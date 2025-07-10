from fastapi import FastAPI, Request, Response, Depends, APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, select, create_engine, SQLModel
from aigc import api, config, models, deps, sessions
from fakeredis import FakeAsyncRedis
import redis.asyncio as redis

router = APIRouter()


# Add a test api to register user and give a trail.
@router.post("/user/register")
async def user_register(
    req: Request, db: Engine = Depends(deps.get_db_engine)
) -> Response:
    body = await req.json()

    user = models.db.User(
        username=body["username"], nickname=body["nickname"], avatar="avatar.jpg"
    )
    with Session(db) as ses:
        ses.add(user)
        ses.commit()
        ses.refresh(user)

    assert user.id
    trail = models.db.MagicPointSubscription(
        uid=user.id, stype=models.db.SubscriptionType.trail, init=30, remains=30
    )
    with Session(db) as ses:
        ses.add(trail)
        ses.commit()

    return JSONResponse(content={"uid": user.id})


# Add a test api to login to make session.
@router.post("/user/login")
async def user_login(
    req: Request,
    db: Engine = Depends(deps.get_db_engine),
    rdb: redis.Redis = Depends(deps.get_rdb),
) -> Response:
    body = await req.json()

    with Session(db) as ses:
        query = select(models.db.User).where(
            models.db.User.username == body["username"]
        )
        user = ses.exec(query).one()
        assert user.id

        tk = await sessions.create_new_session(rdb, user.id, user.nickname)

    return JSONResponse(content={"token": tk})


def make_fake_app() -> FastAPI:
    conf = config.Config()
    conf.magic_points.subscriptions = [
        config.MagicPointSubscription(price=100, month=1, points=1000)
    ]

    connect_args = {"check_same_thread": False}
    engine = create_engine("sqlite://", connect_args=connect_args, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    rdb = FakeAsyncRedis()

    app = FastAPI()

    app.dependency_overrides[config.get_config] = lambda: conf
    app.dependency_overrides[deps.get_db_engine] = lambda: engine
    app.dependency_overrides[deps.get_rdb] = lambda: rdb

    app.include_router(router, prefix="/test")
    app.include_router(api.user.router)

    return app
