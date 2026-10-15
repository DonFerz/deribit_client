from __future__ import annotations

import asyncio
from decimal import Decimal

import aiohttp
import pytest
from aioresponses import aioresponses

from app.clients.deribit_client import DeribitClient
from app.core.exceptions import DeribitClientError
from app.schemas.price import TickerEnum

pytestmark = pytest.mark.asyncio

_BASE_URL = "https://www.deribit.com/api/v2"
_BTC_URL = f"{_BASE_URL}/public/get_index_price?index_name=btc_usd"


@pytest.fixture
def mocked_aiohttp():
    """Контекстный мок для aiohttp.ClientSession.

    Все реальные HTTP-запросы перехватываются и должны быть
    явно зарегистрированы через `mocked.get(...)` — иначе запрос
    упадёт, что удобно для тестов (нет «неожиданных» вызовов).
    """
    with aioresponses() as mock:
        yield mock


async def _call_get_index_price(
    ticker: TickerEnum = TickerEnum.BTC_USD,
) -> Decimal:
    """Вспомогательная обёртка: создаёт ClientSession + клиент и дергает метод.

    Возвращает результат или пробрасывает исключение — тесты
    сами решают, что ожидать.
    """
    async with aiohttp.ClientSession() as session:
        client = DeribitClient(
            session=session,
            base_url=_BASE_URL,
            request_timeout=10,
        )
        return await client.get_index_price(ticker)


async def test_get_index_price_success(mocked_aiohttp) -> None:
    """Успешный ответ Deribit → Decimal с ценой."""
    mocked_aiohttp.get(
        _BTC_URL,
        payload={"result": {"index_price": 50000.5}},
    )

    price = await _call_get_index_price()

    assert price == Decimal("50000.5")
    assert isinstance(price, Decimal)


async def test_get_index_price_preserves_decimal_precision(
    mocked_aiohttp,
) -> None:
    """Цена не «плывёт» после конвертации float → Decimal."""
    mocked_aiohttp.get(
        _BTC_URL,
        payload={"result": {"index_price": 50000.12345678}},
    )

    price = await _call_get_index_price()

    # Decimal(str(float)) должен дать ровно ту строку, что
    # сериализовалась в JSON. Без str() получили бы хвост
    # из двоичного представления.
    assert price == Decimal("50000.12345678")


async def test_get_index_price_uses_correct_query_param(
    mocked_aiohttp,
) -> None:
    """Клиент подставляет `index_name` = значение Enum, а не имя поля."""
    eth_url = f"{_BASE_URL}/public/get_index_price?index_name=eth_usd"
    mocked_aiohttp.get(
        eth_url,
        payload={"result": {"index_price": 3000}},
    )

    price = await _call_get_index_price(TickerEnum.ETH_USD)

    assert price == Decimal("3000")


async def test_get_index_price_http_error(mocked_aiohttp) -> None:
    """Не-200 статус → DeribitClientError с кодом ответа."""
    mocked_aiohttp.get(
        _BTC_URL,
        status=500,
        body="Internal Server Error",
    )

    with pytest.raises(DeribitClientError) as exc_info:
        await _call_get_index_price()

    assert exc_info.value.status_code == 500
    assert "Internal Server Error" in str(exc_info.value)


async def test_get_index_price_timeout(mocked_aiohttp) -> None:
    """Таймаут → DeribitClientError."""
    mocked_aiohttp.get(_BTC_URL, exception=asyncio.TimeoutError())

    with pytest.raises(DeribitClientError) as exc_info:
        await _call_get_index_price()

    assert "timed out" in str(exc_info.value).lower()


async def test_get_index_price_connection_error(mocked_aiohttp) -> None:
    """Сетевая ошибка → DeribitClientError."""
    mocked_aiohttp.get(
        _BTC_URL, exception=aiohttp.ClientConnectionError("refused")
    )

    with pytest.raises(DeribitClientError) as exc_info:
        await _call_get_index_price()

    assert "refused" in str(exc_info.value)


async def test_get_index_price_invalid_json(mocked_aiohttp) -> None:
    """Не-JSON тело → DeribitClientError, а не сырой JSONDecodeError."""
    mocked_aiohttp.get(
        _BTC_URL,
        status=200,
        body="not a json",
        content_type="application/json",
    )

    with pytest.raises(DeribitClientError) as exc_info:
        await _call_get_index_price()

    assert "non-JSON" in str(exc_info.value)


async def test_get_index_price_missing_result_field(
    mocked_aiohttp,
) -> None:
    """Нет `result.index_price` в ответе → DeribitClientError."""
    mocked_aiohttp.get(_BTC_URL, payload={"result": {}})

    with pytest.raises(DeribitClientError) as exc_info:
        await _call_get_index_price()

    assert "structure" in str(exc_info.value).lower()


async def test_get_index_price_error_response_from_deribit(
    mocked_aiohttp,
) -> None:
    """Deribit вернул JSON с `error` вместо `result` → DeribitClientError."""
    mocked_aiohttp.get(
        _BTC_URL,
        payload={"error": {"message": "Invalid index_name"}},
    )

    with pytest.raises(DeribitClientError):
        await _call_get_index_price()


async def test_get_index_price_invalid_price_value(
    mocked_aiohttp,
) -> None:
    """index_price = не число → DeribitClientError."""
    mocked_aiohttp.get(
        _BTC_URL,
        payload={"result": {"index_price": "not-a-number"}},
    )

    with pytest.raises(DeribitClientError) as exc_info:
        await _call_get_index_price()

    assert "Invalid index_price" in str(exc_info.value)
