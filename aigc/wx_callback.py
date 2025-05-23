from fastapi import APIRouter, Request, HTTPException, Header, Response
from sqlmodel import select
from fastapi.responses import RedirectResponse
import requests
from pydantic import BaseModel
from typing import Optional, Annotated
from . import deps, sessions, models
import json


router = APIRouter(prefix="/wx")

HeaderField = Annotated[str, Header()]


class AuthCode(BaseModel):
    code: str
    state: Optional[str] = None


@router.get("/login/callback")
async def wechat_login_callback(
        code: str,
        state: str,
        db: deps.Database,
        rdb: deps.Rdb,
        wx: deps.WxClient):
    """
    微信扫码登录回调接口
    流程 1. 接收code -> 2. 换取access_token -> 3. 获取用户信息
    """

    # 用code换取access_token
    app_id = wx.sec.app_id
    app_secret = wx.sec.app_secret
    token_url = f"https://api.weixin.qq.com/sns/oauth2/access_token?appid={app_id}&secret={app_secret}&code={code}&grant_type=authorization_code"

    try:
        token_res = requests.get(token_url)
        token_data = token_res.json()

        if "errcode" in token_data:
            raise HTTPException(
                status_code=400, detail=f"WeChat API error: {token_data.get('errmsg')}"
            )

        access_token = token_data["access_token"]
        openid = token_data["openid"]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Token exchange failed: {str(e)}")

    # Step 3: 获取用户基本信息
    user_info_url = f"https://api.weixin.qq.com/sns/userinfo?access_token={access_token}&openid={openid}"

    try:
        user_res = requests.get(user_info_url)
        user_data = user_res.json()

        if "errcode" in user_data:
            raise HTTPException(
                status_code=400,
                detail=f"WeChat user API error: {user_data.get('errmsg')}",
            )

        # Read wx user info whio trying to login.
        # Check if wx user already exists.
        req_wxuinfo = models.user.WxUserInfo.model_validate_json(
            user_res.content)
        exists_wxuinfo = db.exec(select(models.user.WxUserInfo).where(
            models.user.WxUserInfo.openid == req_wxuinfo.openid)).one_or_none()

        # If wx user already exists. just do login.
        if exists_wxuinfo is not None:
            user = db.get(models.user.User, exists_wxuinfo.uid)
            assert user is not None

            

        # No wx user, create a new user and associate to this wx user.
        else:

            # Create new user.
            new_user = models.user.User(username=f"wx_{req_wxuinfo.openid}", nickname=req_wxuinfo.nickname,
                                        avatar=req_wxuinfo.avatar, wx_id=req_wxuinfo.openid)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            # Associate user and wx user info then write to database.
            assert new_user.id is not None
            req_wxuinfo.uid = new_user.id
            db.add(req_wxuinfo)
            db.commit()

            token = sessions.create_new_session(rdb, new_user.id)

            # 重定向到前端并携带token
            return RedirectResponse(url=f"{state}?token={token}")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"User info fetch failed: {str(e)}")


@router.post("/pay/callback")
async def wechat_pay_callback(wechatpay_timestamp: HeaderField,
                              wechatpay_nonce: HeaderField,
                              wechatpay_signature: HeaderField,
                              wx: deps.WxClient,
                              request: Request) -> Response:

    body = await request.body()
    if not wx.verify(wechatpay_timestamp, wechatpay_nonce, wechatpay_signature, body.decode()):
        raise HTTPException(status_code=400, detail=json.dumps({
            "code": "FAIL",
            "message": "失败"
        }, ensure_ascii=False))

    print(body)
    return Response()


# @app.get("/api/user/info")
# async def user_info(
#     authorization: Annotated[Union[str, None], Header()] = None,
# ) -> models.user.WxUserInfo:
#     if authorization is None:
#         raise HTTPException(status_code=401, detail=f"No authorization token")

#     (auth_type, token) = authorization.split()
#     if auth_type == "bearer" and token in user_infos.keys():
#         return user_infos[token]

#     raise HTTPException(status_code=401, detail="No authorization token")
