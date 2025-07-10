from unittest import IsolatedAsyncioTestCase
from fastapi.testclient import TestClient
from .fakesrv import app
from http import HTTPStatus


class TestUserAPIs(IsolatedAsyncioTestCase):

    async def test_get_user_info(self) -> None:
        client = TestClient(app)
        client.post("/test/user/register", json={
            "username": "test", "nickname": "admin"
        })
        tk = client.post("/test/user/login", json={"username": "test"})

        resp = client.get("/user/info", headers={"authorization": f"bearer {tk}"})

        self.assertEqual(resp.status_code, HTTPStatus.OK)


