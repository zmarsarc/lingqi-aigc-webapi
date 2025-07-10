from sqlmodel import create_engine, SQLModel
from sqlalchemy import Engine
from . import user, payment, db  # type: ignore


def initialize_database_io(url: str) -> Engine:
    connect_args = {"check_same_thread": False}

    engine = create_engine(url, connect_args=connect_args)

    SQLModel.metadata.create_all(engine)

    return engine
