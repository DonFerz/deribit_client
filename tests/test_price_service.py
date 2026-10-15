from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.exceptions import InvalidDateRangeError, PriceNotFoundError
from app.schemas.price import TickerEnum
from app.services.price_service import PriceCollectorService, PriceQueryService
from tests.fakes import FakePriceClient

pytestmark = pytest.mark.asyncio


# ---------- PriceQueryService ----------


async def test_query_get_all_returns_prices(uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("100"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("200"), 200)

    service = PriceQueryService(uow_factory=uow_factory)
    prices = await service.get_all(TickerEnum.BTC_USD)

    assert [p.timestamp for p in prices] == [100, 200]


async def test_query_get_latest_returns_newest(uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("100"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("300"), 300)

    service = PriceQueryService(uow_factory=uow_factory)
    latest = await service.get_latest(TickerEnum.BTC_USD)

    assert latest.timestamp == 300


async def test_query_get_latest_raises_when_empty(uow_factory) -> None:
    service = PriceQueryService(uow_factory=uow_factory)

    with pytest.raises(PriceNotFoundError) as exc_info:
        await service.get_latest(TickerEnum.BTC_USD)

    assert exc_info.value.ticker == "btc_usd"


async def test_query_get_by_period_raises_on_reversed_range(
    uow_factory,
) -> None:
    service = PriceQueryService(uow_factory=uow_factory)

    date_from = datetime(2025, 1, 2, tzinfo=timezone.utc)
    date_to = datetime(2025, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(InvalidDateRangeError):
        await service.get_by_period(TickerEnum.BTC_USD, date_from, date_to)


async def test_query_get_by_period_open_boundaries(uow_factory) -> None:
    """`None` в границах означает «с начала времён» / «до сейчас»."""
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("2"), 200)

    service = PriceQueryService(uow_factory=uow_factory)
    prices = await service.get_by_period(TickerEnum.BTC_USD, None, None)

    assert len(prices) == 2


async def test_query_get_by_period_filters_by_datetime(uow_factory) -> None:
    """ISO → ms: границы считаются в миллисекундах UTC."""
    async with uow_factory() as uow:
        # 2025-01-01T00:00:00Z = 1735689600000 ms
        base = 1_735_689_600_000
        for offset in (0, 1000, 2000, 3000):
            await uow.prices.add(
                TickerEnum.BTC_USD, Decimal("1"), base + offset
            )

    service = PriceQueryService(uow_factory=uow_factory)
    date_from = datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 1, 1, 0, 0, 2, tzinfo=timezone.utc)

    prices = await service.get_by_period(
        TickerEnum.BTC_USD, date_from, date_to
    )

    # Включительно: 1000 и 2000 ms.
    assert [p.timestamp for p in prices] == [
        1_735_689_601_000,
        1_735_689_602_000,
    ]


async def test_query_get_by_period_naive_datetime_treated_as_utc(
    uow_factory,
) -> None:
    """Naive datetime трактуется как UTC, а не как локальное время."""
    async with uow_factory() as uow:
        await uow.prices.add(
            TickerEnum.BTC_USD, Decimal("1"), 1_735_689_600_000
        )

    service = PriceQueryService(uow_factory=uow_factory)
    naive = datetime(2025, 1, 1, 0, 0, 0)  # без tzinfo
    aware = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    by_naive = await service.get_by_period(TickerEnum.BTC_USD, naive, naive)
    by_aware = await service.get_by_period(TickerEnum.BTC_USD, aware, aware)

    # ORM-объекты из разных сессий сравниваются по identity, а не
    # по полям. Поэтому сравниваем значимые атрибуты.
    assert [(p.ticker, p.price, p.timestamp) for p in by_naive] == [
        (p.ticker, p.price, p.timestamp) for p in by_aware
    ]


# ---------- PriceCollectorService ----------


async def test_collector_saves_all_tickers(uow_factory) -> None:
    client = FakePriceClient()
    client.set_price(TickerEnum.BTC_USD, Decimal("50000"))
    client.set_price(TickerEnum.ETH_USD, Decimal("3000"))

    service = PriceCollectorService(uow_factory=uow_factory, client=client)
    stored = await service.collect_and_store(
        [TickerEnum.BTC_USD, TickerEnum.ETH_USD]
    )

    assert stored == [TickerEnum.BTC_USD, TickerEnum.ETH_USD]

    async with uow_factory() as uow:
        btc = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)
        eth = await uow.prices.get_all_by_ticker(TickerEnum.ETH_USD)

    assert len(btc) == 1 and btc[0].price == Decimal("50000")
    assert len(eth) == 1 and eth[0].price == Decimal("3000")


async def test_collector_uses_single_timestamp_for_batch(
    uow_factory,
) -> None:
    """Все тикеры одного сбора получают одинаковый timestamp."""
    client = FakePriceClient()
    client.set_price(TickerEnum.BTC_USD, Decimal("1"))
    client.set_price(TickerEnum.ETH_USD, Decimal("2"))

    service = PriceCollectorService(uow_factory=uow_factory, client=client)
    await service.collect_and_store(
        [TickerEnum.BTC_USD, TickerEnum.ETH_USD]
    )

    async with uow_factory() as uow:
        btc = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)
        eth = await uow.prices.get_all_by_ticker(TickerEnum.ETH_USD)

    assert btc[0].timestamp == eth[0].timestamp


async def test_collector_partial_success(uow_factory) -> None:
    """Если один тикер упал, второй всё равно сохраняется."""
    client = FakePriceClient()
    client.set_price(TickerEnum.BTC_USD, Decimal("50000"))
    client.set_error(
        TickerEnum.ETH_USD, RuntimeError("Deribit упал по eth")
    )

    service = PriceCollectorService(uow_factory=uow_factory, client=client)
    stored = await service.collect_and_store(
        [TickerEnum.BTC_USD, TickerEnum.ETH_USD]
    )

    assert stored == [TickerEnum.BTC_USD]

    async with uow_factory() as uow:
        eth = await uow.prices.get_all_by_ticker(TickerEnum.ETH_USD)

    assert eth == []


async def test_collector_all_failed_stores_nothing(uow_factory) -> None:
    client = FakePriceClient()
    client.set_error(TickerEnum.BTC_USD, RuntimeError("fail"))

    service = PriceCollectorService(uow_factory=uow_factory, client=client)
    stored = await service.collect_and_store([TickerEnum.BTC_USD])

    assert stored == []

    async with uow_factory() as uow:
        btc = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)

    assert btc == []
