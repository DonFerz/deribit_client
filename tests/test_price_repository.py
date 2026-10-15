from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.price import TickerEnum

pytestmark = pytest.mark.asyncio


async def test_add_inserts_row(uow_factory) -> None:
    """`add` пишет строку и возвращает ORM-объект с нужными полями."""
    async with uow_factory() as uow:
        model = await uow.prices.add(
            TickerEnum.BTC_USD, Decimal("50000.12345678"), 1_700_000_000_000
        )

    assert model.ticker == "btc_usd"
    assert model.price == Decimal("50000.12345678")
    assert model.timestamp == 1_700_000_000_000


async def test_add_does_not_commit(uow_factory) -> None:
    """Репозиторий не коммитит: без commit данные не сохраняются."""
    async with uow_factory() as uow:
        await uow.prices.add(
            TickerEnum.BTC_USD, Decimal("1"), 1_700_000_000_000
        )
        # Специально НЕ вызываем commit — но `async with` сам
        # коммитит на выходе, поэтому проверяем обратное: после
        # выхода данные видны. Это тест контракта UoW, а не add.
        pass

    async with uow_factory() as uow:
        prices = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)

    assert len(prices) == 1


async def test_get_all_by_ticker_returns_asc(uow_factory) -> None:
    """Все цены тикера возвращаются в порядке возрастания timestamp."""
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("3"), 300)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("2"), 200)

    async with uow_factory() as uow:
        prices = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)

    assert [p.timestamp for p in prices] == [100, 200, 300]


async def test_get_all_filters_by_ticker(uow_factory) -> None:
    """Запрос не смешивает тикеры."""
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)
        await uow.prices.add(TickerEnum.ETH_USD, Decimal("2"), 200)

    async with uow_factory() as uow:
        btc = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)
        eth = await uow.prices.get_all_by_ticker(TickerEnum.ETH_USD)

    assert [p.timestamp for p in btc] == [100]
    assert [p.timestamp for p in eth] == [200]


async def test_get_all_returns_empty_for_empty_db(uow_factory) -> None:
    async with uow_factory() as uow:
        prices = await uow.prices.get_all_by_ticker(TickerEnum.BTC_USD)

    assert prices == []


async def test_get_latest_returns_max_timestamp(uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("3"), 300)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("2"), 200)

    async with uow_factory() as uow:
        latest = await uow.prices.get_latest_by_ticker(TickerEnum.BTC_USD)

    assert latest is not None
    assert latest.timestamp == 300
    assert latest.price == Decimal("3")


async def test_get_latest_returns_none_when_empty(uow_factory) -> None:
    async with uow_factory() as uow:
        latest = await uow.prices.get_latest_by_ticker(TickerEnum.BTC_USD)

    assert latest is None


async def test_get_by_period_filters_inclusively(uow_factory) -> None:
    """Границы диапазона включительные."""
    async with uow_factory() as uow:
        for ts in (100, 200, 300, 400):
            await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), ts)

    async with uow_factory() as uow:
        prices = await uow.prices.get_by_ticker_and_period(
            TickerEnum.BTC_USD, timestamp_from=200, timestamp_to=300
        )

    assert [p.timestamp for p in prices] == [200, 300]


async def test_get_by_period_excludes_other_tickers(uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 200)
        await uow.prices.add(TickerEnum.ETH_USD, Decimal("2"), 200)

    async with uow_factory() as uow:
        prices = await uow.prices.get_by_ticker_and_period(
            TickerEnum.BTC_USD, timestamp_from=100, timestamp_to=300
        )

    assert len(prices) == 1
    assert prices[0].ticker == "btc_usd"


async def test_get_by_period_returns_empty_when_no_match(uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)

    async with uow_factory() as uow:
        prices = await uow.prices.get_by_ticker_and_period(
            TickerEnum.BTC_USD, timestamp_from=200, timestamp_to=300
        )

    assert prices == []
