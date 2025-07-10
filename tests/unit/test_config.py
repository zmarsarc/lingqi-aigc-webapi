from unittest import TestCase, mock
from aigc import config
from typing import Any, IO
from dataclasses import asdict

fake_web_conf: dict[str, Any] = {
    "host": "0.0.0.0",
    "port": 9090,
    "session_ttl": 7200,
}

fake_redis_conf: dict[str, Any] = {"host": "127.0.0.1", "port": 6379, "db": 0}

fake_database_conf: dict[str, Any] = {"url": "sqlite:///dbfile.db"}

fake_wechat_secret_conf: dict[str, Any] = {
    "login_id": "fake login id",
    "app_id": "fake app id",
    "app_secret": "fake app secret",
    "mch_id": "fake mch id",
    "mch_cert_serial": "fake mch cert serial",
    "pub_key_id": "fake pub key id",
    "api_v3_pwd": "fake api v3 pwd",
    "api_client_key_path": "fake_apiclient_key.pem",
    "pub_key_path": "fake_pub_key.pem",
}

fake_pem_data: dict[str, Any] = {
    "api_client_key": b"fake api client key file data.",
    "pub_key": b"fake pub key file data.",
}

fake_wechat_conf: dict[str, Any] = {
    "login_redirect": "https://www.lingqi.tech/aigc/api/wx/login/callback",
    "payment_callback": "https://www.lingqi.tech/aigc/api/wx/pay/callback",
    "payment_expires": 300,
    "secrets": fake_wechat_secret_conf | fake_pem_data,
}

fake_magic_point_subscription: dict[str, Any] = {
    "price": 9900,
    "month": 1,
    "points": 1000,
}

fake_magic_point_conf: dict[str, Any] = {
    "trail_free_point": 100,
    "subscriptions": [{"price": 1, "month": 12, "points": 500}],
}

fake_infer_conf: dict[str, Any] = {
    "long_poll_timeout": 60,
    "base": "abc",
    "replace_any": "def",
    "replace_reference": "foo",
    "segment_any": "bar",
    "image_to_video": "test",
    "edit_with_prompt": "ewp"
}

fake_config: dict[str, Any] = {
    "web": fake_web_conf,
    "redis": fake_redis_conf,
    "database": fake_database_conf,
    "wechat": fake_wechat_conf,
    "magic_points": fake_magic_point_conf,
    "infer": fake_infer_conf,
}


def read_fake_pem(fname: str, mode: str) -> IO[Any]:
    fake_files: dict[str, bytes] = {
        fake_wechat_secret_conf["api_client_key_path"]: fake_pem_data["api_client_key"],
        fake_wechat_secret_conf["pub_key_path"]: fake_pem_data["pub_key"],
    }
    return mock.mock_open(read_data=fake_files[fname])()


class TestConfig(TestCase):

    def test_load_web_config(self):
        conf = config.WebConfig.load(fake_web_conf)
        self.assertEqual(asdict(conf), fake_web_conf)

    def test_load_redis_config(self):
        conf = config.RedisConfig.load(fake_redis_conf)
        self.assertEqual(asdict(conf), fake_redis_conf)

    def test_load_database_config(self):
        conf = config.DatabaseConfig.load(fake_database_conf)
        self.assertEqual(asdict(conf), fake_database_conf)

    @mock.patch("builtins.open")
    def test_load_wechat_secrets_config(self, mocker: mock.MagicMock):
        mocker.side_effect = read_fake_pem
        conf = config.WechatSecretConfig.load(fake_wechat_secret_conf)

        mocker.assert_has_calls(
            [
                mock.call(fake_wechat_secret_conf["api_client_key_path"], "rb"),
                mock.call(fake_wechat_secret_conf["pub_key_path"], "rb"),
            ]
        )
        self.assertEqual(
            asdict(conf),
            fake_wechat_secret_conf | fake_pem_data,
        )

    @mock.patch("builtins.open")
    def test_load_wechat_config(self, mocker: mock.MagicMock):
        mocker.side_effect = read_fake_pem
        conf = config.WechatConfig.load(fake_wechat_conf)
        self.assertEqual(asdict(conf), fake_wechat_conf)

    def test_load_magic_point_subscription(self):
        conf = config.MagicPointSubscription.load(fake_magic_point_subscription)
        self.assertEqual(asdict(conf), fake_magic_point_subscription)

    def test_load_magic_point_conf(self):
        conf = config.MagicPointConfig.load(fake_magic_point_conf)
        self.assertEqual(asdict(conf), fake_magic_point_conf)

    def test_load_infer_conf(self):
        conf = config.InferConfig.load(fake_infer_conf)
        self.assertEqual(asdict(conf), fake_infer_conf)

    @mock.patch("builtins.open")
    def test_load_config(self, mocker: mock.MagicMock):
        mocker.side_effect = read_fake_pem

        conf = config.Config.load(fake_config)
        self.assertEqual(asdict(conf), fake_config)
