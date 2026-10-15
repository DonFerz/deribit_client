from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import Price
from app.repositories.base import AbstractPriceRepository
from app.schemas.price import TickerEnum


class SQLAlchemyPriceRepository(AbstractPriceRepository):
    """Реализация репозитория цен на SQLAlchemy 2.0 (async)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, ticker: TickerEnum, price: Decimal, timestamp: int
    ) -> Price:
        """Сохраняет новую цену и возвращает ORM-объект.

        Делает `flush`, а не `commit` — вызывающий сам решает,
        когда фиксировать транзакцию.
        """
        model = Price(ticker=ticker.value, price=price, timestamp=timestamp)
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_all_by_ticker(self, ticker: TickerEnum) -> list[Price]:
        """Все сохранённые цены тикера, отсортированные по timestamp (asc)."""
        stmt = (
            select(Price)
            .where(Price.ticker == ticker.value)
            .order_by(Price.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_ticker(self, ticker: TickerEnum) -> Price | None:
        """Последняя сохранённая цена тикера, либо None."""
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
        timestamp_from: int,
        timestamp_to: int,
    ) -> list[Price]:
        """Цены тикера в интервале [timestamp_from, timestamp_to] (ms UTC).

        Границы включительные. Сортировка по timestamp (asc).
        """
        stmt = (
            select(Price)
            .where(
                Price.ticker == ticker.value,
                Price.timestamp >= timestamp_from,
                Price.timestamp <= timestamp_to,
            )
            .order_by(Price.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
