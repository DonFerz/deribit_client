from __future__ import annotations

from datetime import datetime

__all__ = [
    "DomainError",
    "TickerNotFoundError",
    "PriceNotFoundError",
    "InvalidDateRangeError",
    "DeribitClientError",
]


class DomainError(Exception):
    """Базовый класс для ошибок"""


class TickerNotFoundError(DomainError):
    """Вызывается, когда запрашиваемый тикер не поддерживается"""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"Ticker '{ticker}' is not supported")


class PriceNotFoundError(DomainError):
    """Вызывается, если для данного тикера нет сохраненных цен"""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"No prices found for ticker '{ticker}'")


class InvalidDateRangeError(DomainError):
    """Вызывается, когда `date_from` не предшествует `date_to`."""

    def __init__(self, date_from: datetime, date_to: datetime) -> None:
        self.date_from = date_from
        self.date_to = date_to
        super().__init__(
            f"'from' ({date_from.isoformat()}) must be earlier than "
            f"'to' ({date_to.isoformat()})"
        )


class DeribitClientError(DomainError):
    """Вызывается, когда Deribit API возвращает неожиданный ответ."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)
