from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.dependencies import PriceQueryServiceDep
from app.schemas.price import (
    LatestPriceResponse,
    PriceListResponse,
    PriceRead,
    TickerEnum,
)

_TICKER_QUERY = Query(
    ...,
    description="Тикер валюты (btc_usd | eth_usd)",
    examples=["btc_usd"],
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get(
    "/all",
    response_model=PriceListResponse,
    summary="Все сохранённые цены по тикеру",
)
async def get_all_prices(
    ticker: Annotated[TickerEnum, _TICKER_QUERY],
    service: PriceQueryServiceDep,
) -> PriceListResponse:
    """Возвращает все сохранённые записи о ценах указанного тикера.

    Сортировка — по возрастанию timestamp. Пустой список —
    валидный ответ (200 с `prices: []`).
    """
    prices = await service.get_all(ticker)
    return PriceListResponse(
        ticker=ticker,
        prices=[PriceRead.model_validate(p) for p in prices],
    )


@router.get(
    "/latest",
    response_model=LatestPriceResponse,
    summary="Последняя цена по тикеру",
    responses={404: {"description": "Данных по тикеру ещё нет"}},
)
async def get_latest_price(
    ticker: Annotated[TickerEnum, _TICKER_QUERY],
    service: PriceQueryServiceDep,
) -> LatestPriceResponse:
    """Возвращает последнюю сохранённую цену тикера.

    Если данных по тикеру ещё нет — 404 (маппинг
    `PriceNotFoundError` в `main.py`).
    """
    price = await service.get_latest(ticker)
    return LatestPriceResponse(
        ticker=ticker,
        price=price.price,
        timestamp=price.timestamp,
    )


@router.get(
    "/by-period",
    response_model=PriceListResponse,
    summary="Цены по тикеру за период",
    responses={
        400: {"description": "Некорректный диапазон дат (from > to)"},
    },
)
async def get_prices_by_period(
    ticker: Annotated[TickerEnum, _TICKER_QUERY],
    service: PriceQueryServiceDep,
    date_from: Annotated[
        AwareDatetime | None,
        Query(
            alias="from",
            description=(
                "Начало периода, ISO 8601 (UTC), включительно. "
                "Если не задано — считается от начала времён."
            ),
            examples=["2025-01-01T00:00:00Z"],
        ),
    ] = None,
    date_to: Annotated[
        AwareDatetime | None,
        Query(
            alias="to",
            description=(
                "Конец периода, ISO 8601 (UTC), включительно. "
                "Если не задано — считается до текущего момента."
            ),
            examples=["2025-01-02T00:00:00Z"],
        ),
    ] = None,
) -> PriceListResponse:
    """Возвращает цены тикера в заданном диапазоне дат.

    Границы включительные. Если `from` или `to` не заданы —
    граница считается открытой (0 или текущий момент
    соответственно). Если `from > to` — 400 (маппинг
    `InvalidDateRangeError`).
    """
    prices = await service.get_by_period(ticker, date_from, date_to)
    return PriceListResponse(
        ticker=ticker,
        prices=[PriceRead.model_validate(p) for p in prices],
    )
