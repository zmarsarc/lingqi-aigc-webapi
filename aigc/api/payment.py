from fastapi import APIRouter, HTTPException, Depends
from .. import deps, wx, models, config, common, sessions
from loguru import logger
from datetime import datetime, timedelta
from sqlmodel import select, Session

router = APIRouter(prefix="/payment")


@router.post("/open")
async def open_payment(
    req: models.payment.OpenPaymentRequest,
    ses: sessions.Session = Depends(deps.get_user_session),
    db: Session = Depends(deps.get_db_session),
    conf: config.Config = Depends(config.get_config),
    wx_client: wx.client.WxClient = Depends(deps.get_wxclient),
) -> models.payment.OpenPaymentResponse:

    # Check subscription plans.
    subplan: config.MagicPointSubscription | None = None
    for p in conf.magic_points.subscriptions:
        if p.price == req.amount:
            subplan = p
            break

    if not subplan:
        raise HTTPException(
            400, f"pay amount {req.amount} can not find a match subscription plan."
        )

    dt = datetime.now()
    tradeid = wx.make_nonce_str(16)
    desc = f"充值 {subplan.price / 100} 开通 {subplan.month} 月会员"
    expires_in = dt + timedelta(seconds=conf.wechat.payment_expires)

    logger.info(
        f"user open new recharge order {tradeid}, amount {req.amount / 100} CNY"
    )

    order = wx.models.Order(
        description=desc,
        out_trade_no=tradeid,
        notify_url=conf.wechat.payment_callback,
        amount=wx.models.PayAmount(total=req.amount),
        time_expire=common.dt.format_datetime(expires_in),
    )

    url = await wx_client.open_transaction(order)
    logger.info(f"recharge order {tradeid} pay url: {url}")

    payment = models.db.Recharge(
        uid=ses.uid,
        tradeid=tradeid,
        amount=req.amount,
        create_time=dt,
        expires=expires_in,
    )
    db.add(payment)
    db.commit()

    return models.payment.OpenPaymentResponse(url=url, tradeid=tradeid)


@router.get("/state", dependencies=[Depends(deps.get_user_session)])
async def get_payment_state(
    tradeid: str,
    db: Session = Depends(deps.get_db_session),
) -> models.payment.GetPaymentStateResponse:

    order = db.exec(
        select(models.db.Recharge).where(models.db.Recharge.tradeid == tradeid)
    ).one_or_none()
    if order is None:
        logger.error(f"no such recharge order which trade id is {tradeid}")
        raise HTTPException(status_code=400, detail="no such trade id.")

    return models.payment.GetPaymentStateResponse(
        tradeid=tradeid, state=order.pay_state, desc=order.reason
    )
