from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.price import TickerEnum

pytestmark = pytest.mark.asyncio


# ---------- /health ----------


async def test_health(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------- /api/v1/prices/all ----------


async def test_all_returns_empty_list(client) -> None:
    """Пустая БД — валидный ответ 200 с пустым списком."""
    response = await client.get("/api/v1/prices/all", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"ticker": "btc_usd", "prices": []}


async def test_all_returns_saved_prices(client, uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("50000"), 1_700_000_000_000)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("51000"), 1_700_000_060_000)

    response = await client.get("/api/v1/prices/all", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "btc_usd"
    assert len(body["prices"]) == 2

    prices = [Decimal(item["price"]) for item in body["prices"]]
    timestamps = [item["timestamp"] for item in body["prices"]]

    assert prices == [Decimal("50000"), Decimal("51000")]
    assert timestamps == [1_700_000_000_000, 1_700_000_060_000]


async def test_all_filters_by_ticker(client, uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)
        await uow.prices.add(TickerEnum.ETH_USD, Decimal("2"), 200)

    response = await client.get("/api/v1/prices/all", params={"ticker": "eth_usd"})

    body = response.json()
    assert body["ticker"] == "eth_usd"
    assert len(body["prices"]) == 1
    assert Decimal(body["prices"][0]["price"]) == Decimal("2")


async def test_all_requires_ticker(client) -> None:
    """Без обязательного query-параметра ticker — 422 от FastAPI."""
    response = await client.get("/api/v1/prices/all")

    assert response.status_code == 422


async def test_all_rejects_unknown_ticker(client) -> None:
    """Неизвестный тикер — 422 (не наша ошибка, валидация FastAPI)."""
    response = await client.get("/api/v1/prices/all", params={"ticker": "doge_usd"})

    assert response.status_code == 422


# ---------- /api/v1/prices/latest ----------


async def test_latest_returns_newest(client, uow_factory) -> None:
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("100"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("300"), 300)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("200"), 200)

    response = await client.get(
        "/api/v1/prices/latest", params={"ticker": "btc_usd"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "btc_usd"
    assert Decimal(body["price"]) == Decimal("300")
    assert body["timestamp"] == 300


async def test_latest_returns_404_when_empty(client) -> None:
    """Нет данных — PriceNotFoundError маппится в 404."""
    response = await client.get(
        "/api/v1/prices/latest", params={"ticker": "btc_usd"}
    )

    assert response.status_code == 404
    assert "btc_usd" in response.json()["detail"]


async def test_latest_requires_ticker(client) -> None:
    response = await client.get("/api/v1/prices/latest")

    assert response.status_code == 422


# ---------- /api/v1/prices/by-period ----------


async def test_by_period_returns_prices_in_range(client, uow_factory) -> None:
    """2025-01-01T00:00:00Z = 1735689600000 ms."""
    base = 1_735_689_600_000
    async with uow_factory() as uow:
        for offset in (0, 1_000, 2_000, 3_000):
            await uow.prices.add(
                TickerEnum.BTC_USD, Decimal("1"), base + offset
            )

    response = await client.get(
        "/api/v1/prices/by-period",
        params={
            "ticker": "btc_usd",
            "from": "2025-01-01T00:00:01Z",
            "to": "2025-01-01T00:00:02Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    timestamps = [item["timestamp"] for item in body["prices"]]
    assert timestamps == [base + 1_000, base + 2_000]


async def test_by_period_without_bounds_returns_all(client, uow_factory) -> None:
    """Без `from`/`to` — открытые границы, возвращаются все данные."""
    async with uow_factory() as uow:
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("1"), 100)
        await uow.prices.add(TickerEnum.BTC_USD, Decimal("2"), 200)

    response = await client.get(
        "/api/v1/prices/by-period", params={"ticker": "btc_usd"}
    )

    assert response.status_code == 200
    assert len(response.json()["prices"]) == 2


async def test_by_period_invalid_range_returns_400(
    client, uow_factory,
) -> None:
    """from > to → InvalidDateRangeError маппится в 400."""
    response = await client.get(
        "/api/v1/prices/by-period",
        params={
            "ticker": "btc_usd",
            "from": "2025-01-02T00:00:00Z",
            "to": "2025-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 400
    assert "earlier" in response.json()["detail"]


async def test_by_period_naive_datetime_rejected(client) -> None:
    """AwareDatetime требует tzinfo — naive строка отклоняется на входе.

    Это часть контракта API: сервис умеет работать с naive,
    но снаружи мы требуем явный offset, чтобы избежать
    неоднозначности.
    """
    response = await client.get(
        "/api/v1/prices/by-period",
        params={
            "ticker": "btc_usd",
            "from": "2025-01-01T00:00:00",
            "to": "2025-01-02T00:00:00",
        },
    )

    assert response.status_code == 422


async def test_by_period_requires_ticker(client) -> None:
    response = await client.get("/api/v1/prices/by-period")

    assert response.status_code == 422


# ---------- OpenAPI ----------


async def test_openapi_includes_all_endpoints(client) -> None:
    """Все три метода + /health присутствуют в OpenAPI-схеме."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/prices/all" in paths
    assert "/api/v1/prices/latest" in paths
    assert "/api/v1/prices/by-period" in paths
