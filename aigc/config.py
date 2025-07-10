import tomllib
from functools import cache
from dataclasses import dataclass, field
from typing import Any

_default_filepath: str = "config.template.toml"


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    session_ttl: int = 3600

    @staticmethod
    def load(toml: dict[str, Any]) -> "WebConfig":
        host: str = toml["host"]
        port: int = int(toml["port"])
        session_ttl: int = int(toml["session_ttl"])

        return WebConfig(host=host, port=port, session_ttl=session_ttl)


@dataclass
class RedisConfig:
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0

    @staticmethod
    def load(toml: dict[str, Any]) -> "RedisConfig":
        host: str = toml["host"]
        port: int = int(toml["port"])
        db: int = int(toml["db"])

        return RedisConfig(host=host, port=port, db=db)


@dataclass
class DatabaseConfig:
    url: str = field(default_factory=lambda: _default_filepath)

    @staticmethod
    def load(toml: dict[str, Any]) -> "DatabaseConfig":
        file: str = toml["file"]
        return DatabaseConfig(url=file)


@dataclass
class WechatSecretConfig:
    login_id: str = ""
    app_id: str = ""
    app_secret: str = ""
    mch_id: str = ""
    mch_cert_serial: str = ""
    pub_key_id: str = ""
    api_v3_pwd: str = ""
    api_client_key_path: str = ""
    pub_key_path: str = ""

    api_client_key: bytes = b""
    pub_key: bytes = b""

    @staticmethod
    def load(toml: dict[str, Any]) -> "WechatSecretConfig":

        login_id: str = toml["login_id"]
        app_id: str = toml["app_id"]
        app_secret: str = toml["app_secret"]
        mch_id: str = toml["mch_id"]
        mch_cert_serial: str = toml["mch_cert_serial"]
        pub_key_id: str = toml["pub_key_id"]
        api_v3_pwd: str = toml["api_v3_pwd"]
        api_client_key_path: str = toml["api_client_key_path"]
        pub_key_path: str = toml["pub_key_path"]

        with open(api_client_key_path, "rb") as fp:
            api_client_key: bytes = fp.read()

        with open(pub_key_path, "rb") as fp:
            pub_key: bytes = fp.read()

        return WechatSecretConfig(
            login_id=login_id,
            app_id=app_id,
            app_secret=app_secret,
            mch_id=mch_id,
            mch_cert_serial=mch_cert_serial,
            pub_key_id=pub_key_id,
            api_v3_pwd=api_v3_pwd,
            api_client_key_path=api_client_key_path,
            pub_key_path=pub_key_path,
            api_client_key=api_client_key,
            pub_key=pub_key,
        )


@dataclass
class WechatConfig:
    secrets: WechatSecretConfig = field(default_factory=WechatSecretConfig)
    login_redirect: str = "/aigc/api/wx/login/callback"
    payment_callback: str = "/aigc/api/wx/pay/callback"
    payment_expires: int = 300

    @staticmethod
    def load(toml: dict[str, Any]) -> "WechatConfig":
        login_redirect: str = toml["login_redirect"]
        payment_callback: str = toml["payment_callback"]
        payment_expires: int = int(toml["payment_expires"])

        return WechatConfig(
            secrets=WechatSecretConfig.load(toml["secrets"]),
            login_redirect=login_redirect,
            payment_callback=payment_callback,
            payment_expires=payment_expires,
        )


@dataclass
class MagicPointSubscription:
    price: int
    month: int
    points: int

    @staticmethod
    def load(toml: dict[str, Any]) -> "MagicPointSubscription":
        return MagicPointSubscription(
            price=int(toml["price"]),
            month=int(toml["month"]),
            points=int(toml["points"]),
        )


@dataclass
class MagicPointConfig:
    trail_free_point: int = 30
    subscriptions: list[MagicPointSubscription] = field(
        default_factory=lambda: [
            MagicPointSubscription(price=9900, month=1, points=1000),
            MagicPointSubscription(price=29900, month=12, points=1000),
        ]
    )

    @staticmethod
    def load(toml: dict[str, Any]) -> "MagicPointConfig":
        return MagicPointConfig(
            trail_free_point=int(toml["trail_free_point"]),
            subscriptions=[
                MagicPointSubscription.load(t) for t in toml["subscriptions"]
            ],
        )


@dataclass
class InferConfig:
    long_poll_timeout: int = 30

    base: str = "http://localhost:8991"
    replace_any: str = "/replace_any"
    replace_reference: str = "/replace_with_reference"
    segment_any: str = "/segment_any"
    image_to_video: str = "/image_to_video"
    edit_with_prompt: str = "/edit_with_prompt"

    @staticmethod
    def load(toml: dict[str, Any]) -> "InferConfig":
        return InferConfig(
            base=toml["base"],
            long_poll_timeout=int(toml["long_poll_timeout"]),
            replace_any=toml["replace_any"],
            replace_reference=toml["replace_reference"],
            segment_any=toml["segment_any"],
            image_to_video=toml["image_to_video"],
            edit_with_prompt=toml["edit_with_prompt"]
        )


# Just read this config when needed.
@dataclass
class Config:
    web: WebConfig = field(default_factory=WebConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    wechat: WechatConfig = field(default_factory=WechatConfig)
    magic_points: MagicPointConfig =field(default_factory=MagicPointConfig)
    infer: InferConfig = field(default_factory=InferConfig)

    @staticmethod
    def load(toml: dict[str, Any]) -> "Config":
        return Config(
            web=WebConfig.load(toml["web"]),
            redis=RedisConfig.load(toml["redis"]),
            database=DatabaseConfig.load(toml["database"]),
            wechat=WechatConfig.load(toml["wechat"]),
            magic_points=MagicPointConfig.load(toml["magic_points"]),
            infer=InferConfig.load(toml["infer"]),
        )


@cache
def get_config(filepath: str | None = None) -> Config:
    if filepath is None:
        filepath = _default_filepath

    with open(filepath, "rb") as fp:
        toml = tomllib.load(fp)

    return Config.load(toml)


def set_config_file_path(path: str):
    global _default_filepath
    _default_filepath = path
    reload_config()


def reload_config() -> None:
    get_config.cache_clear()
