from fastapi import APIRouter, Depends
from pydantic import BaseModel
from .. import sessions, deps, models
from sqlmodel import Session, select, desc, func
from sqlalchemy import Engine
from typing import Any
import json


class InferenceDetail(BaseModel):
    tid: str
    type: str
    state: str
    ctime: str
    utime: str
    request: Any | None = None
    response: Any | None = None


class InferenceHistoryItem(BaseModel):
    tid: str
    type: str
    state: str
    ctime: str
    utime: str


class GetInferenceHistoryWithPage(BaseModel):
    start: int
    count: int
    total: int
    history: list[InferenceHistoryItem]


class APIResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    data: GetInferenceHistoryWithPage | InferenceDetail | None = None


router = APIRouter(prefix="/gallery")


@router.get("/history")
async def get_inference_history(
    start: int,
    count: int,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
) -> APIResponse:

    selection = (
        select(models.db.InferenceLog)
        .where(models.db.InferenceLog.uid == ses.uid)
        .where(models.db.InferenceLog.type != models.db.InferenceType.segment_any)
        .order_by(desc(models.db.InferenceLog.ctime))
        .offset(start)
        .limit(count)
    )

    count_query = (
        select(func.count())
        .select_from(models.db.InferenceLog)
        .where(models.db.InferenceLog.uid == ses.uid)
        .where(models.db.InferenceLog.type != models.db.InferenceType.segment_any)
    )

    with Session(db) as dbsession:
        total = dbsession.exec(count_query).one()
        history = dbsession.exec(selection).all()

    result = GetInferenceHistoryWithPage(
        start=start, count=count, total=total, history=[]
    )
    for row in history:
        h = InferenceHistoryItem(
            tid=row.tid,
            type=str(row.type),
            state=str(row.state),
            ctime=row.ctime.strftime("%Y-%m-%d %H:%M:%S"),
            utime=row.utime.strftime("%Y-%m-%d %H:%M:%S"),
        )
        result.history.append(h)
    return APIResponse(data=result)

# TODO need to handle key error.
@router.get("/detail/{tid}")
async def get_inference_detail(
    tid: str,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Session = Depends(deps.get_db_session),
) -> APIResponse:
    query = (
        select(models.db.InferenceLog)
        .where(models.db.InferenceLog.uid == ses.uid)
        .where(models.db.InferenceLog.tid == tid)
    )
    log = db.exec(query).one_or_none()
    if log is None:
        raise KeyError("no such inference request.")

    h = InferenceDetail(
        tid=log.tid,
        type=str(log.type),
        state=str(log.state),
        ctime=log.ctime.strftime("%Y-%m-%d %H:%M:%S"),
        utime=log.utime.strftime("%Y-%m-%d %H:%M:%S"),
        request={},
        response={},
    )
    if log.request != "":
        h.request = json.loads(log.request)
    if log.response != "":
        h.response = json.loads(log.response)

    return APIResponse(data=h)


@router.delete(
    "/history/{tid}", response_model=APIResponse, response_model_exclude_none=True
)
async def delete_inference_history(
    tid: str,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Engine = Depends(deps.get_db),
) -> APIResponse:
    query = (
        select(models.db.InferenceLog)
        .where(models.db.InferenceLog.uid == ses.uid)
        .where(models.db.InferenceLog.tid == tid)
    )

    with Session(db) as dbsession:
        ilog = dbsession.exec(query).one_or_none()

    if ilog is not None:
        dbsession.delete(ilog)
        dbsession.commit()
        return APIResponse()

    return APIResponse(code=1, msg="no such inference history")
