from unittest import IsolatedAsyncioTestCase
from .fakesrv import make_fake_app
from fastapi.testclient import TestClient
from http import HTTPStatus


class TestUserAPIs(IsolatedAsyncioTestCase):

    async def test_get_user_info(self) -> None:
        client = TestClient(make_fake_app())
        client.post("/test/user/register", json={"username": "abc", "nickname": "def"})
        tk = client.post("/test/user/login", json={"username": "abc"}).json()["token"]

        resp = client.get("/user/info", headers={"authorization": f"bearer {tk}"})
        self.assertEqual(resp.status_code, HTTPStatus.OK)

        self.assertEqual(
            resp.json(),
            {
                "username": "abc",
                "nickname": "def",
                "avatar": "avatar.jpg",
                "point": 30,
                "is_member": False,
                "expires_in": None,
            },
        )
