from sqlmodel import create_engine, SQLModel
from sqlalchemy import Engine
from . import user

def initialize_database_io(db_file_name: str) -> Engine:
    sqlite_url = f"sqlite:///{db_file_name}"
    connect_args = {"check_same_thread": False}

    engine = create_engine(sqlite_url, connect_args=connect_args)

    SQLModel.metadata.create_all(engine)

    return engine
