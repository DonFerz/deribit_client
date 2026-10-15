from __future__ import annotations

from decimal import Decimal

from app.clients.base import AbstractPriceClient
from app.schemas.price import TickerEnum


class FakePriceClient(AbstractPriceClient):
    """Тестовый клиент биржи.

    Не делает HTTP-запросов: цены и ошибки задаются заранее через
    `set_price` / `set_error`. Также фиксирует историю обращений —
    удобно проверять, что сервис дёрнул клиент по нужным тикерам.
    """

    def __init__(self) -> None:
        self._prices: dict[TickerEnum, Decimal] = {}
        self._errors: dict[TickerEnum, Exception] = {}
        self.calls: list[TickerEnum] = []

    def set_price(self, ticker: TickerEnum, price: Decimal) -> None:
        """Задаёт цену, которую вернёт клиент для тикера."""
        self._prices[ticker] = price

    def set_error(self, ticker: TickerEnum, error: Exception) -> None:
        """Задаёт исключение, которое бросит клиент для тикера."""
        self._errors[ticker] = error

    async def get_index_price(self, ticker: TickerEnum) -> Decimal:
        """Возвращает заданную цену или бросает заданную ошибку."""
        self.calls.append(ticker)
        if ticker in self._errors:
            raise self._errors[ticker]
        if ticker not in self._prices:
            raise RuntimeError(
                f"FakePriceClient: не задана цена для тикера {ticker.value}"
            )
        return self._prices[ticker]
