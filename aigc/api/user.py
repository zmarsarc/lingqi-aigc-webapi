from fastapi import APIRouter, Depends
from .. import deps, models, sessions
from sqlmodel import select, Session
from datetime import datetime

router = APIRouter(prefix="/user")


@router.get("/info")
async def user_info(
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Session = Depends(deps.get_db_session),
) -> models.user.GetUserInfoResponse:
    userinfo = db.get_one(models.db.User, ses.uid)
    subscription = db.exec(
        select(models.db.MagicPointSubscription)
        .where(models.db.MagicPointSubscription.uid == ses.uid)
        .where(models.db.MagicPointSubscription.expired == False)
    ).all()

    # Subscription should have only one.
    expires_in: datetime | None = None
    point_in_today: int = 0
    is_member = False

    for s in [
        s for s in subscription if s.stype == models.db.SubscriptionType.subscription
    ]:
        if s.expired == True:
            continue

        expires_in = s.expires_in
        is_member = True
        point_in_today += s.remains

    if not is_member:
        for s in [
            s for s in subscription if s.stype == models.db.SubscriptionType.trail
        ]:
            point_in_today += s.remains

    return models.user.GetUserInfoResponse(
        username=userinfo.username,
        nickname=userinfo.nickname,
        avatar=userinfo.avatar,
        point=point_in_today,
        expires_in=expires_in,
        is_member=is_member,
    )
