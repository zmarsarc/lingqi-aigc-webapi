import uvicorn
from aigc import config, models, wx, deps, router
from argparse import ArgumentParser
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI


def main() -> None:
    # Load default config, default can overwrite by env variables.
    default_config = config.Config()

    # Parse command line arguments.
    parser = ArgumentParser()
    parser.add_argument(
        "secret", help="The secret file which contain senstive data like appid."
    )
    parser.add_argument("apiclient_key_file",
                        help="path to the api client key file from wx.")
    parser.add_argument("pub_key_file", help="path to the wx pub key file.")
    parser.add_argument(
        "--host", help="WEB API host address", default=default_config.api_host
    )
    parser.add_argument("--port", help="WEB API port",
                        default=default_config.api_port)
    arguments = parser.parse_args()
    secret, apiclient_key, pub_key = arguments.secret, arguments.apiclient_key_file, arguments.pub_key_file

    # Make app lifespan manager.
    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        sec = wx.must_load_secert(
            secerts=secret,
            apiclient_key=apiclient_key,
            pub_key=pub_key)
        deps.set_wx_client_deps(app, sec)

        engine = models.initialize_database_io(default_config.database_file)
        deps.set_db_session_deps(app, engine)

        conn_pool = redis.ConnectionPool(
            host=default_config.redis_host,
            port=default_config.redis_port,
            db=default_config.redis_db,
            decode_responses=True
        )
        rdb = redis.Redis(connection_pool=conn_pool)
        deps.set_rdb_deps(app, rdb)

        yield

        await conn_pool.aclose()

    app = FastAPI(lifespan=app_lifespan)
    app.include_router(router)

    try:
        uvicorn.run(app, host=arguments.host, port=arguments.port)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
