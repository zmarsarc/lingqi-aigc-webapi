from sqlalchemy import Engine
from sqlmodel import Session, select
from datetime import datetime, timedelta
from loguru import logger
from . import models
import asyncio

# FIXME: when near middle, it may return 0 second delay.
def delay_to_next_middle_night(now: datetime) -> int:
    next_middlenight = now.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    delay_s = (next_middlenight - now).seconds
    return delay_s


def refresh_subscriptions(db: Engine, dt: datetime):
    with Session(db) as ses:
        subscriptions = ses.exec(
            select(models.db.MagicPointSubscription).where(
                models.db.MagicPointSubscription.expired == False
            )
        ).all()

        # Refresh subscriptions, if exipre, set state.
        for s in subscriptions:
            s.utime = dt

            if s.expires_in is not None and dt > s.expires_in:
                s.expired = True

            else:
                s.remains = s.init

        log = models.db.SubscriptionsRefreshLog(refresh_time=dt, cnt=len(subscriptions))

        ses.add(log)
        ses.commit()

    logger.info(f"refresh subscrptions, total {len(subscriptions)}")


async def refresh_forever(db: Engine, delay_s: int):
    try:
        while True:
            await asyncio.sleep(delay_s)
            now = datetime.now()
            refresh_subscriptions(db, now)
            delay_s = delay_to_next_middle_night(now)
            logger.debug(f"next refresh {delay_s} seconds after.")

    except asyncio.CancelledError:
        logger.info("refresh subscriptions task canceled.")
        return


def arrage_refresh_subscriptions(db: Engine) -> asyncio.Task[None]:

    now = datetime.now()
    this_middle_night = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Check if already refreshed today.
    with Session(db) as ses:
        logs = ses.exec(
            select(models.db.SubscriptionsRefreshLog).where(
                models.db.SubscriptionsRefreshLog.refresh_time >= this_middle_night
            )
        ).all()

    # If no refresh log today, refresh immediate.
    if len(logs) == 0:
        refresh_subscriptions(db, now)

    # Arrage next fresh.
    delay_s = delay_to_next_middle_night(now)
    logger.debug(f"next refresh {delay_s} seconds after.")

    return asyncio.create_task(refresh_forever(db, delay_s))
