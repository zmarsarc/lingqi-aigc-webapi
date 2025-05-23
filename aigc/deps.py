from typing import Annotated, Generator
from fastapi import Depends, Request, FastAPI
from sqlmodel import Session
from .wx import secret, client
from sqlalchemy import Engine
import redis.asyncio as redis


def set_db_session_deps(app: FastAPI, engine: Engine):
    app.state.engine = engine


def set_wx_client_deps(app: FastAPI, secret: secret.WxSecrets):
    wx_client = client.new_client(secerts=secret)
    app.state.wx_client = wx_client


def set_rdb_deps(app: FastAPI, rdb: redis.Redis):
    app.state.rdb = rdb


def get_session(req: Request) -> Generator[Session, None, None]:
    with Session(req.app.state.engine) as s:
        yield s


def get_wx_client(req: Request) -> client.WxClient:
    return req.app.state.wx_client


def get_rdb(req: Request) -> redis.Redis:
    return req.app.state.rdb


Database = Annotated[Session, Depends(get_session)]

WxClient = Annotated[client.WxClient, Depends(get_wx_client)]

Rdb = Annotated[redis.Redis, Depends(get_rdb)]
