from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from app.clients.base import AbstractPriceClient
from app.core.config import get_settings
from app.core.exceptions import DeribitClientError
from app.core.logging import get_logger
from app.schemas.price import TickerEnum

logger = get_logger(__name__)

_INDEX_PRICE_PATH = "/public/get_index_price"
_MAX_BODY_IN_ERROR = 200


class DeribitClient(AbstractPriceClient):
    """Клиент публичного REST API Deribit на aiohttp.

    Принимает `aiohttp.ClientSession` снаружи: клиент не управляет
    жизненным циклом соединений. Это позволяет создавать
    короткоживущую сессию на каждый Celery-таск (свой event loop).

    Клиент stateless относительно данных — только читает с биржи.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        request_timeout: int,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._request_timeout = request_timeout
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)

    @classmethod
    def from_settings(cls, session: aiohttp.ClientSession) -> "DeribitClient":
        """Фабрика: собирает клиент из настроек приложения."""
        settings = get_settings()
        return cls(
            session=session,
            base_url=settings.deribit_base_url,
            request_timeout=settings.deribit_request_timeout,
        )

    async def get_index_price(self, ticker: TickerEnum) -> Decimal:
        """Запрашивает index-цену тикера у Deribit.

        Бросает `DeribitClientError` при сетевой ошибке, таймауте,
        ненулевом HTTP-статусе или неожиданной структуре ответа.
        """
        url = f"{self._base_url}{_INDEX_PRICE_PATH}"
        params = {"index_name": ticker.value}

        try:
            payload = await self._fetch(url, params=params)
        except DeribitClientError as exc:
            logger.warning(
                "Deribit request failed",
                extra={"ticker": ticker.value, "url": url, "error": str(exc)},
            )
            raise

        raw_price = self._extract_index_price(payload)
        return self._to_decimal(raw_price)

    async def _fetch(
        self,
        url: str,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Выполняет GET-запрос и возвращает распарсенный JSON."""
        try:
            async with self._session.get(
                url, params=params, timeout=self._timeout
            ) as response:
                body = await response.text()
                if response.status != 200:
                    raise DeribitClientError(
                        f"Deribit returned HTTP {response.status}: "
                        f"{body[:_MAX_BODY_IN_ERROR]}",
                        status_code=response.status,
                    )
                try:
                    return await response.json(content_type=None)
                except (aiohttp.ContentTypeError, json.JSONDecodeError) as exc:
                    raise DeribitClientError(
                        f"Deribit returned non-JSON response: "
                        f"{body[:_MAX_BODY_IN_ERROR]!r}"
                    ) from exc
        except asyncio.TimeoutError as exc:
            raise DeribitClientError(
                f"Deribit request timed out after {self._request_timeout}s"
            ) from exc
        except aiohttp.ClientError as exc:
            raise DeribitClientError(f"Failed to reach Deribit: {exc}") from exc

    @staticmethod
    def _extract_index_price(payload: dict[str, Any]) -> object:
        """Достаёт поле `result.index_price` из ответа Deribit."""
        try:
            return payload["result"]["index_price"]
        except (KeyError, TypeError) as exc:
            raise DeribitClientError(
                f"Unexpected Deribit response structure: {payload!r}"
            ) from exc

    @staticmethod
    def _to_decimal(raw_price: object) -> Decimal:
        """Конвертирует сырое значение в Decimal.

        Deribit присылает index_price как JSON-число (float).
        `Decimal(str(value))` сохраняет ровно те знаки, что пришли
        по проводу — без float-хвостов.
        """
        try:
            return Decimal(str(raw_price))
        except (InvalidOperation, ValueError) as exc:
            raise DeribitClientError(
                f"Invalid index_price value: {raw_price!r}"
            ) from exc
