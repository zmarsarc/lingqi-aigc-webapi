from fastapi import (
    APIRouter,
    Depends,
    Response,
    Request,
    BackgroundTasks,
    HTTPException,
)
from functools import cache
from typing import Mapping, TypeAlias
from collections.abc import Callable, Awaitable

from ... import deps, config, sessions, models
from pydantic import BaseModel
import httpx
from .common import (
    get_current_subscription,
    point_manager,
    PointManager,
    NoPointError,
    InferResponse,
    InferRoute,
    NotDownError,
    CancelError,
)
import asyncio
from dataclasses import dataclass, field
import secrets
from loguru import logger
from http import HTTPStatus
from sqlmodel import Session, select
from sqlalchemy import Engine
from datetime import datetime
import json


STATE_WAITING: str = "waiting"
STATE_IN_PROGRESS: str = "in progress"
STATE_DOWN: str = "down"


# Normal response.
class APIResponse(BaseModel):
    code: int
    msg: str


# Response model when append new request and query requests state.
class GetStateResponse(BaseModel):
    code: int
    msg: str
    tid: str
    index: int
    state: str


# Response model when create new background task.
class CreateRequestResponse(BaseModel):
    code: int
    msg: str
    tid: str


# Define background request metadata.
@dataclass
class BackgroundRequest:
    exception: Exception | None = field(default=None, init=False)
    response: Response | None = field(default=None, init=False)
    cond: asyncio.Condition = field(default_factory=asyncio.Condition, init=False)


RequestFunc: TypeAlias = Callable[
    [str, bytes, Mapping[str, str], Engine], Awaitable[None]
]


# TODO: need to remove expired request data.
# Class use to manage background requests.
class BackgroundRequestsDict:

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.cond = asyncio.Condition()
        self.request_list: list[BackgroundRequest] = []
        self.responses_by_uid: dict[int, dict[str, BackgroundRequest]] = {}

    async def new_request(self, uid: int, point: int) -> tuple[str, RequestFunc]:
        tid: str = secrets.token_hex(8)
        task = BackgroundRequest()

        async with self.cond:
            self.request_list.append(task)
            if uid not in self.responses_by_uid:
                self.responses_by_uid[uid] = {}
            self.responses_by_uid[uid][tid] = task
            self.cond.notify_all()

        async def worker(
            url: str, content: bytes, headers: Mapping[str, str], db: Engine
        ) -> None:
            ses = Session(db)
            ilog = ses.exec(
                select(models.db.InferenceLog).where(models.db.InferenceLog.tid == tid)
            ).one()

            try:
                # This part, wait this task be the first at the queue,
                # or canceled, both will break waiting.
                # If cancel, it will raise a CancelError.
                async with self.cond:
                    logger.debug(f"infer request {tid} waiting")
                    await self.cond.wait_for(
                        lambda: task not in self.request_list
                        or self.request_list.index(task) == 0
                    )
                    if task not in self.request_list:
                        raise CancelError(tid)

                # From now, task can go on.
                # Update inference log first.
                logger.debug(f"infer request {tid} in progress")
                ilog.state = models.db.InferenceState.in_progress
                ilog.request = content.decode()
                ilog.utime = datetime.now()
                ses.add(ilog)
                ses.commit()

                # Send infer request.
                async with httpx.AsyncClient(timeout=None) as client:
                    resp = await client.post(url, content=content, headers=headers)
                    logger.debug(f"infer server response request {tid}")

                # Check response, if infer result code not equal to 0, give point back.
                resp.raise_for_status()
                response = InferResponse.model_validate_json(resp.content)
                if response.code != 0:
                    async with point_manager(uid, ses) as pm:
                        pm.recharge(point)
                        logger.info("inference srv not success, recharge point.")

                ilog.state = models.db.InferenceState.down
                ilog.response = resp.content.decode()
                ilog.utime = datetime.now()
                ses.add(ilog)
                ses.commit()

                # Set infer result.
                async with task.cond:
                    task.response = Response(content=resp.content, headers=resp.headers)
                    task.cond.notify_all()

            except Exception as exc:
                logger.error(f"background request encounter error, {str(exc)}")

                if isinstance(exc, CancelError):
                    ilog.state = models.db.InferenceState.canceled
                else:
                    ilog.state = models.db.InferenceState.failed
                ilog.utime = datetime.now()
                ses.add(ilog)
                ses.commit()

                # If have exception, recharge point as well.
                async with point_manager(uid, ses) as pm:
                    pm.recharge(point)
                    logger.info(f"request error, recharge point.")

                async with task.cond:
                    task.exception = exc
                    task.cond.notify_all()

            finally:
                ses.close()
                async with self.cond:
                    if task in self.request_list:
                        self.request_list.remove(task)
                    self.cond.notify_all()

                logger.debug(f"infer request {tid} down.")

        return (tid, worker)


# A function to build requests dict with cache.
# Due to the arguments always the same so it always return same object.
@cache
def get_requests_dict() -> BackgroundRequestsDict:
    return BackgroundRequestsDict()


# A dependence function to get a new point manager.
async def get_point_manager(
    ses: sessions.Session = Depends(deps.get_user_session),
    dbses: Session = Depends(deps.get_db_session),
) -> PointManager:

    sub = await get_current_subscription(ses.uid, dbses)
    mgr = PointManager(sub, dbses)
    return mgr


# Define router
router = APIRouter(prefix="/async/infer", route_class=InferRoute)


# API to query background requests current state, no block.
@router.get("/{tid}/state")
async def get_req_state(
    tid: str,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
) -> GetStateResponse:

    response = GetStateResponse(
        code=0, msg="ok", tid=tid, index=0, state=STATE_IN_PROGRESS
    )

    try:
        async with req_dict.lock:
            infer_request = req_dict.responses_by_uid[ses.uid][tid]
            idx = req_dict.request_list.index(infer_request)
            if idx != 0:
                response.index = idx
                response.state = STATE_WAITING
                return response
            if infer_request.exception or infer_request.response:
                response.state = STATE_DOWN

    except (ValueError, KeyError):
        with Session(db) as dbsession:
            ilog = dbsession.exec(
                select(models.db.InferenceLog)
                .where(models.db.InferenceLog.uid == ses.uid)
                .where(models.db.InferenceLog.tid == tid)
            ).one_or_none()

            if ilog is None:
                raise KeyError()

            response.state = str(ilog.state)

    return response


# API to get result of a request if have, no block.
@router.get("/{tid}/result")
async def get_req_result(
    tid: str,
    ses: sessions.Session = Depends(deps.get_user_session),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
) -> Response:

    async with req_dict.lock:
        infer_request = req_dict.responses_by_uid[ses.uid][tid]

        if infer_request.exception:
            raise infer_request.exception

        if infer_request.response:
            return infer_request.response

        raise NotDownError(tid)


# API to long poll inference request result.
@router.get("/{tid}/result/wait")
async def wait_req_result(
    tid: str,
    ses: sessions.Session = Depends(deps.get_user_session),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
    conf: config.Config = Depends(config.get_config),
) -> Response:
    async with req_dict.lock:
        infer_requests = req_dict.responses_by_uid[ses.uid][tid]

    async with infer_requests.cond:

        try:
            async with asyncio.timeout(conf.infer.long_poll_timeout):
                await infer_requests.cond.wait_for(
                    lambda: infer_requests.response or infer_requests.exception
                )
        except TimeoutError:
            pass

        if infer_requests.exception:
            raise infer_requests.exception

        if infer_requests.response:
            return infer_requests.response

        return Response(status_code=HTTPStatus.NO_CONTENT)


# API to cancel waiting request
@router.post("/{tid}/cancel")
async def cancel_waiting_request(
    tid: str,
    ses: sessions.Session = Depends(deps.get_user_session),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
) -> APIResponse:

    async with req_dict.cond:
        infer_request = req_dict.responses_by_uid[ses.uid][tid]

        try:
            idx = req_dict.request_list.index(infer_request)
            if idx != 0:
                req_dict.request_list.remove(infer_request)
                req_dict.cond.notify_all()

        except ValueError:
            pass

    return APIResponse(code=0, msg="task canceled")


# API to create a background replace with any infer request.
@router.post("/replace_any")
async def replace_with_any(
    req: Request,
    bg: BackgroundTasks,
    ses: sessions.Session = Depends(deps.get_user_session),
    pm: PointManager = Depends(get_point_manager),
    db: Engine = Depends(deps.get_db),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
    conf: config.Config = Depends(config.get_config),
) -> CreateRequestResponse:

    point = 10
    if pm.magic_points < point:
        raise NoPointError(ses.uid)
    pm.deduct(point)

    tid, worker = await req_dict.new_request(ses.uid, point)

    ilog = models.db.InferenceLog(
        uid=ses.uid,
        tid=tid,
        type=models.db.InferenceType.replace_with_any,
    )

    with Session(db) as cursor:
        cursor.add(ilog)
        cursor.commit()

    url = conf.infer.base + conf.infer.replace_any
    bg.add_task(worker, url, await req.body(), req.headers, db)

    return CreateRequestResponse(code=0, msg="ok", tid=tid)


# API to create a background replace with reference infer request.
@router.post("/replace_with_reference")
async def replace_with_reference(
    req: Request,
    bg: BackgroundTasks,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
    pm: PointManager = Depends(get_point_manager),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
    conf: config.Config = Depends(config.get_config),
) -> CreateRequestResponse:

    if pm.magic_points < 10:
        raise NoPointError(ses.uid)
    pm.deduct(10)

    tid, worker = await req_dict.new_request(ses.uid, 10)

    ilog = models.db.InferenceLog(
        uid=ses.uid,
        tid=tid,
        type=models.db.InferenceType.replace_with_reference,
    )

    with Session(db) as cursor:
        cursor.add(ilog)
        cursor.commit()

    url = conf.infer.base + conf.infer.replace_reference
    bg.add_task(worker, url, await req.body(), req.headers, db)

    return CreateRequestResponse(code=0, msg="ok", tid=tid)


# API to create a background image to video request.
@router.post("/image_to_video")
async def image_to_video(
    req: Request,
    bg: BackgroundTasks,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
    pm: PointManager = Depends(get_point_manager),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
    conf: config.Config = Depends(config.get_config),
) -> CreateRequestResponse:
    point = 30

    if pm.magic_points < point:
        raise NoPointError(ses.uid)
    pm.deduct(point)

    tid, worker = await req_dict.new_request(ses.uid, point)

    ilog = models.db.InferenceLog(
        uid=ses.uid,
        tid=tid,
        type=models.db.InferenceType.image_to_video,
    )

    with Session(db) as cursor:
        cursor.add(ilog)
        cursor.commit()

    url = conf.infer.image_to_video
    bg.add_task(worker, url, await req.body(), req.headers, db)

    return CreateRequestResponse(code=0, msg="ok", tid=tid)


# API to create a background segment any infer request.
@router.post("/segment_any")
async def segment_any(
    req: Request,
    bg: BackgroundTasks,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
    pm: PointManager = Depends(get_point_manager),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
    conf: config.Config = Depends(config.get_config),
) -> CreateRequestResponse:

    point = 1

    if pm.magic_points < point:
        raise NoPointError(ses.uid)
    pm.deduct(point)

    tid, worker = await req_dict.new_request(ses.uid, point)

    ilog = models.db.InferenceLog(
        uid=ses.uid,
        tid=tid,
        type=models.db.InferenceType.segment_any,
    )

    with Session(db) as cursor:
        cursor.add(ilog)
        cursor.commit()

    url = conf.infer.base + conf.infer.segment_any
    bg.add_task(worker, url, await req.body(), req.headers, db)

    return CreateRequestResponse(code=0, msg="ok", tid=tid)


# API to create a background edit with prompt infer request.
@router.post("/edit_with_prompt")
async def edit_with_prompt(
    req: Request,
    bg: BackgroundTasks,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
    pm: PointManager = Depends(get_point_manager),
    req_dict: BackgroundRequestsDict = Depends(get_requests_dict),
    conf: config.Config = Depends(config.get_config),
) -> CreateRequestResponse:
    normal_mode_point = 10
    enhance_mode_point = 15

    try:
        req_body = await req.json()
        if "enhance" in req_body and req_body["enhance"] == True:
            point = enhance_mode_point
        else:
            point = normal_mode_point
    except json.JSONDecodeError:
        raise HTTPException(422, detail="must have request body")

    if pm.magic_points < point:
        raise NoPointError(ses.uid)
    pm.deduct(point)

    tid, worker = await req_dict.new_request(ses.uid, point)

    ilog = models.db.InferenceLog(
        uid=ses.uid, tid=tid, type=models.db.InferenceType.edit_with_prompt
    )

    with Session(db) as cursor:
        cursor.add(ilog)
        cursor.commit()

    url = conf.infer.base + conf.infer.edit_with_prompt
    bg.add_task(worker, url, await req.body(), req.headers, db)

    return CreateRequestResponse(code=0, msg="ok", tid=tid)
