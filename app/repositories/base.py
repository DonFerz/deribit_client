from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.models.price import Price
from app.schemas.price import TickerEnum


class AbstractPriceRepository(ABC):
    """Интерфейс репозитория цен.

    Сервисный слой зависит только от этого интерфейса — конкретная
    реализация (SQLAlchemy, in-memory, мок в тестах) подставляется
    извне.

    Реализация НЕ коммитит транзакцию: вызывающий сам управляет
    границами транзакции (сервис или Celery-таск).
    """

    @abstractmethod
    async def add(
        self, ticker: TickerEnum, price: Decimal, timestamp: int
    ) -> Price:
        """Сохраняет новую цену и возвращает ORM-объект.

        Не коммитит. Вызывающий должен явно вызвать commit.
        """

    @abstractmethod
    async def get_all_by_ticker(self, ticker: TickerEnum) -> list[Price]:
        """Возвращает все сохранённые цены тикера, отсортированные по timestamp (asc)."""

    @abstractmethod
    async def get_latest_by_ticker(self, ticker: TickerEnum) -> Price | None:
        """Возвращает последнюю сохранённую цену тикера, либо None."""

    @abstractmethod
    async def get_by_ticker_and_period(
        self,
        ticker: TickerEnum,
        timestamp_from: int,
        timestamp_to: int,
    ) -> list[Price]:
        """Возвращает цены тикера в интервале [timestamp_from, timestamp_to],
        отсортированные по timestamp (asc).
        """
