from fastapi import Depends, HTTPException, Header, Request, FastAPI
from sqlalchemy import Engine
from sqlmodel import Session
import redis.asyncio as redis
from . import sessions, config, wx
from collections.abc import Iterator


def get_app(req: Request) -> FastAPI:
    return req.app


def get_db(app: FastAPI = Depends(get_app)) -> Engine:
    return app.state.db


def get_db_session(db: Engine = Depends(get_db)) -> Iterator[Session]:
    with Session(db) as ses:
        yield ses


def get_rdb(app: FastAPI = Depends(get_app)) -> redis.Redis:
    return app.state.rdb


async def get_user_session(
    rdb: redis.Redis = Depends(get_rdb), authorization: str = Header()
) -> sessions.Session:
    auth_type, token = authorization.split(" ")
    if auth_type != "bearer" or token == "":
        raise HTTPException(status_code=401, detail="no valid authorization to access.")

    ses = await sessions.get_session_or_none(rdb, token)
    if ses is None:
        raise HTTPException(status_code=401, detail="no valid authorization to access.")

    # Refersh session automaticly when have valid session.
    await sessions.refresh_session(rdb, token)
    return ses


def get_wxclient(
    conf: config.Config = Depends(config.get_config),
) -> wx.client.WxClient:
    return wx.client.new_client(conf.wechat.secrets)
