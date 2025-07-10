from typing import Annotated
from collections.abc import Iterator
from fastapi import Depends, HTTPException, Header
from sqlmodel import Session
from sqlalchemy import Engine
import redis.asyncio as redis
from . import sessions, config, wx, models

from functools import cache


def get_db_file_path(conf: config.Config = Depends(config.get_config)) -> str:
    return conf.database.url


def get_rdb_host(conf: config.Config = Depends(config.get_config)) -> str:
    return conf.redis.host


def get_rdb_port(conf: config.Config = Depends(config.get_config)) -> int:
    return conf.redis.port


def get_rdb_db(conf: config.Config = Depends(config.get_config)) -> int:
    return conf.redis.db


@cache
def get_db_engine(filepath: str = Depends(get_db_file_path)) -> Engine:
    return models.initialize_database_io(filepath)


@cache
def get_rdb(
    host: str = Depends(get_rdb_host),
    port: int = Depends(get_rdb_port),
    db: int = Depends(get_rdb_db)
) -> redis.Redis:
    return redis.Redis(host=host, port=port, db=db, decode_responses=True)


def get_db_session(engine: Engine = Depends(get_db_engine)) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


HeaderField = Annotated[str, Header()]


def get_auth_token(authorization: HeaderField) -> str:
    auth_type, token = authorization.split(" ")
    if auth_type != "bearer" or token == "":
        raise HTTPException(
            status_code=401, detail="no valid authorization to access.")
    return token


Rdb = Annotated[redis.Redis, Depends(get_rdb)]

AuthToken = Annotated[str, Depends(get_auth_token)]


async def get_user_session(rdb: Rdb, token: AuthToken) -> sessions.Session:
    ses = await sessions.get_session_or_none(rdb, token)
    if ses is None:
        raise HTTPException(
            status_code=401, detail="no valid authorization to access.")

    # Refersh session automaticly when have valid session.
    await sessions.refresh_session(rdb, token)
    return ses


UserSession = Annotated[sessions.Session, Depends(get_user_session)]


def get_wxclient(
    conf: config.Config = Depends(config.get_config),
) -> wx.client.WxClient:
    return wx.client.new_client(conf.wechat.secrets)
