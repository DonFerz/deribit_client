from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TickerEnum(str, Enum):
    """Поддерживаемые тикеры Deribit."""
    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"


class PriceRead(BaseModel):
    """Схема одной записи о цене."""
    model_config = ConfigDict(from_attributes=True)

    ticker: TickerEnum
    price: Decimal = Field(..., gt=0)
    timestamp: int = Field(
        ...,
        gt=0,
        description="UNIX timestamp в миллисекундах UTC (как отдаёт Deribit)",
    )


class PriceListResponse(BaseModel):
    """Ответ со списком цен по указанному тикеру."""
    ticker: TickerEnum
    prices: list[PriceRead]


class LatestPriceResponse(BaseModel):
    """Ответ с последней сохранённой ценой по тикеру."""
    ticker: TickerEnum
    price: Decimal
    timestamp: int


class PriceFilterQuery(BaseModel):
    """Фильтр по диапазону дат для истории цен."""
    date_from: datetime | None = Field(
        None, description="Начало диапазона (UTC, ISO 8601, включительно)"
    )
    date_to: datetime | None = Field(
        None, description="Конец диапазона (UTC, ISO 8601, включительно)"
    )

    @model_validator(mode="after")
    def _check_range(self) -> "PriceFilterQuery":
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from must be earlier than date_to")
        return self
