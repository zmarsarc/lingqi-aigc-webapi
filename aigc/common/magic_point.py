from ..models.db import MagicPointSubscription, SubscriptionType
from sqlalchemy import Engine
from sqlmodel import Session, select

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator


class Manager:

    def __init__(self, db: Engine) -> None:
        self._db: Engine = db

    @asynccontextmanager
    async def current_subscription(self, uid: int) -> AsyncIterator[MagicPointSubscription]:
        with Session(self._db) as ses:
            subscription = ses.exec(
                select(MagicPointSubscription)
                .where(MagicPointSubscription.uid == uid)
                .where(MagicPointSubscription.stype == SubscriptionType.subscription)
                .where(MagicPointSubscription.expired == False)
            ).one_or_none()

            if subscription is None:
                subscription = ses.exec(
                    select(MagicPointSubscription)
                    .where(MagicPointSubscription.uid == uid)
                    .where(MagicPointSubscription.stype == SubscriptionType.trail)
                ).one()

            yield subscription

            ses.commit()
