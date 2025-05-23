from pydantic_settings import BaseSettings


class Config(BaseSettings):
    api_host: str = "127.0.0.1"
    api_port: int = 8090

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    
    database_file: str = "database.db"

    session_ttl_s: int = 3600
