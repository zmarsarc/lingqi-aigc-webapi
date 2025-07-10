from unittest import IsolatedAsyncioTestCase, mock
from .fakesrv import make_fake_app
from fastapi.testclient import TestClient
from aigc.api.infer import async_infer
from http import HTTPStatus
from httpx import Response, Request


class TestInferAPIs(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.app = make_fake_app()
        self.client = TestClient(self.app)

        # Registe test user and login.
        self.client.post(
            "/test/user/register", json={"username": "abc", "nickname": "def"}
        )
        resp = self.client.post("/test/user/login", json={"username": "abc"})
        self.token = resp.json()["token"]

    @mock.patch.object(async_infer.httpx.AsyncClient, "post", autospec=True)
    async def test_replace_any(self, mocker: mock.MagicMock):
        mocker.return_value = Response(
            request=Request("POST", url=""),
            status_code=200,
            json={"code": 0, "msg": "ok"},
        )

        resp = self.client.post(
            "/async/infer/replace_any",
            json={},
            headers={"authorization": f"bearer {self.token}", "some": "data"},
        )

        self.assertEqual(resp.status_code, HTTPStatus.OK)
        body = resp.json()
        self.assertDictContainsSubset({"code": 0, "msg": "ok"}, body)

        tid = body["tid"]

        resp = self.client.get(
            f"/async/infer/{tid}/state",
            headers={"authorization": f"bearer {self.token}"},
        )
        self.assertDictContainsSubset(
            {"code": 0, "msg": "ok", "tid": tid, "index": 0, "state": "down"},
            resp.json(),
        )

        resp = self.client.get(
            f"/async/infer/{tid}/result",
            headers={"authorization": f"bearer {self.token}"},
        )
        self.assertDictContainsSubset({"code": 0, "msg": "ok"}, resp.json())

        resp = self.client.get(
            "/user/info", headers={"authorization": f"bearer {self.token}"}
        )
        self.assertDictContainsSubset({"point": 20}, resp.json())
