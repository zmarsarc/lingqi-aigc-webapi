from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=128)
    nickname: str = Field(max_length=128)
    avatar: str
    phone: str | None = None
    wx_id: str | None = Field(default=None, index=True)


class WxUserInfo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    openid: str = Field(index=True)
    uid: int = Field(index=True)
    avatar: str
    nickname: str
    unionid: str
