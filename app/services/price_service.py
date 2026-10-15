from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime

from app.clients.base import AbstractPriceClient
from app.core.exceptions import InvalidDateRangeError, PriceNotFoundError
from app.core.logging import get_logger
from app.core.time import datetime_to_unix_ms, now_unix_ms
from app.models.price import Price
from app.repositories.uow import AbstractUnitOfWork
from app.schemas.price import TickerEnum

logger = get_logger(__name__)


class PriceQueryService:
    """Read-only операции над сохранёнными ценами.

    Нужен только Unit of Work — сервис не подозревает о
    существовании биржи, HTTP или Celery.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    async def get_all(self, ticker: TickerEnum) -> list[Price]:
        """Возвращает все сохранённые цены тикера (asc по времени)."""
        async with self._uow_factory() as uow:
            return await uow.prices.get_all_by_ticker(ticker)

    async def get_latest(self, ticker: TickerEnum) -> Price:
        """Возвращает последнюю сохранённую цену тикера.

        Бросает `PriceNotFoundError`, если данных по тикеру нет.
        """
        async with self._uow_factory() as uow:
            price = await uow.prices.get_latest_by_ticker(ticker)

        if price is None:
            raise PriceNotFoundError(ticker.value)
        return price

    async def get_by_period(
        self,
        ticker: TickerEnum,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Price]:
        """Возвращает цены тикера в заданном диапазоне (границы включительны).

        `None` в `date_from` трактуется как «с начала времён»,
        `None` в `date_to` — как «до текущего момента».
        Бросает `InvalidDateRangeError`, если `date_from > date_to`.
        """
        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise InvalidDateRangeError(date_from, date_to)

        ts_from = datetime_to_unix_ms(date_from) if date_from else 0
        ts_to = datetime_to_unix_ms(date_to) if date_to else now_unix_ms()

        async with self._uow_factory() as uow:
            return await uow.prices.get_by_ticker_and_period(
                ticker, ts_from, ts_to
            )


class PriceCollectorService:
    """Сбор index-цен с биржи и сохранение их в БД.

    Используется только Celery-задачей. Знает про клиент биржи,
    но ничего не знает про HTTP-слой.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        client: AbstractPriceClient,
    ) -> None:
        self._uow_factory = uow_factory
        self._client = client

    async def collect_and_store(
        self, tickers: Sequence[TickerEnum]
    ) -> list[TickerEnum]:
        """Забирает index-цены у биржи и сохраняет их одной транзакцией.

        Падение по одному тикеру не мешает сохранить остальные.
        Возвращает список успешно сохранённых тикеров.
        """
        # Timestamp фиксируется до запроса: это момент инициации сбора,
        # единый для всех тикеров в одном батче.
        now_ms = now_unix_ms()

        fetched = await asyncio.gather(
            *(self._client.get_index_price(ticker) for ticker in tickers),
            return_exceptions=True,
        )

        stored: list[TickerEnum] = []

        async with self._uow_factory() as uow:
            for ticker, result in zip(tickers, fetched, strict=True):
                if isinstance(result, asyncio.CancelledError):
                    # Отмена должна распространяться — не глотаем её.
                    raise result
                if isinstance(result, BaseException):
                    logger.error(
                        "Failed to fetch index price from Deribit",
                        extra={"ticker": ticker.value, "error": str(result)},
                    )
                    continue
                await uow.prices.add(ticker, result, now_ms)
                stored.append(ticker)

        if len(stored) < len(tickers):
            logger.warning(
                "Partial success collecting index prices",
                extra={
                    "total": len(tickers),
                    "stored": [t.value for t in stored],
                    "failed": [
                        t.value for t in tickers if t not in stored
                    ],
                    "timestamp_ms": now_ms,
                },
            )
        else:
            logger.info(
                "Index prices stored",
                extra={
                    "tickers": [t.value for t in stored],
                    "timestamp_ms": now_ms,
                },
            )

        return stored
