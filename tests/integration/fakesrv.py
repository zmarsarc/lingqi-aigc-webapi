from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlmodel import Session, select
from aigc import api, config, models, deps, sessions
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import random
from threading import Thread
from fakeredis import TcpFakeServer
import secrets
import redis.asyncio as redis


fakeredis_port = random.randint(10000, 60000)


def mock_get_config() -> config.Config:
    conf = config.Config()
    conf.magic_points.subscriptions = [
        config.MagicPointSubscription(price=100, month=1, points=1000)
    ]
    conf.database.url = f"sqlite:////tmp/{secrets.token_hex(4)}.db"
    conf.redis.port = fakeredis_port

    return conf


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    server_address = ("127.0.0.1", fakeredis_port)
    server = TcpFakeServer(server_address, server_type="redis")
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()

    yield

    server.shutdown()


app = FastAPI(lifespan=app_lifespan)

app.dependency_overrides[config.get_config] = mock_get_config

app.include_router(api.user.router)


# Add a test api to register user and give a trail.
@app.post("/test/user/register")
async def user_register(req: Request, db: Engine = Depends(deps.get_db_engine)) -> Response:
    body = await req.json()

    user = models.db.User(
            username=body["username"],
            nickname=body["nickname"],
            avatar="avatar.jpg")
    with Session(db) as ses:
        ses.add(user)
        ses.commit()
        ses.refresh(user)

    assert user.id
    trail = models.db.MagicPointSubscription(
        uid=user.id,
        stype=models.db.SubscriptionType.trail,
        init=30, remains=30
    )
    with Session(db) as ses:
        ses.add(trail)
        ses.commit()

    return JSONResponse(content={"uid": user.id})


# Add a test api to login to make session.
@app.post("/test/user/login")
async def user_login(req: Request, db: Engine = Depends(deps.get_db_engine), rdb: redis.Redis = Depends(deps.get_rdb)) -> Response:
    body = await req.json()
    
    with Session(db) as ses:
        query = select(models.db.User).where(
            models.db.User.username == body["username"])
        user = ses.exec(query).one()
        assert user.id

        tk = await sessions.create_new_session(rdb, user.id, user.nickname)

    return JSONResponse(content={"token": tk})
