from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import Price
from app.repositories.base import AbstractPriceRepository
from app.schemas.price import TickerEnum


def _datetime_to_unix_seconds(dt: datetime) -> int:
    """Конвертирует datetime в UNIX timestamp (секунды).

    Naive datetime трактуется как UTC — это защищает от
    случайного применения локальной таймзоны сервера.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


class SQLAlchemyPriceRepository(AbstractPriceRepository):
    """Реализация репозитория цен на SQLAlchemy 2.0 (async)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, ticker: TickerEnum, price: Decimal, timestamp: int
    ) -> Price:
        model = Price(ticker=ticker.value, price=price, timestamp=timestamp)
        self._session.add(model)
        # flush, а не commit: транзакцией управляет сервисный слой.
        await self._session.flush()
        return model

    async def get_all_by_ticker(self, ticker: TickerEnum) -> list[Price]:
        stmt = (
            select(Price)
            .where(Price.ticker == ticker.value)
            .order_by(Price.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_ticker(self, ticker: TickerEnum) -> Price | None:
        stmt = (
            select(Price)
            .where(Price.ticker == ticker.value)
            .order_by(Price.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ticker_and_period(
        self,
        ticker: TickerEnum,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Price]:
        from_ts = _datetime_to_unix_seconds(date_from)
        to_ts = _datetime_to_unix_seconds(date_to)

        stmt = (
            select(Price)
            .where(
                Price.ticker == ticker.value,
                Price.timestamp >= from_ts,
                Price.timestamp <= to_ts,
            )
            .order_by(Price.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
