from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.schemas.price import TickerEnum


class AbstractPriceClient(ABC):
    """Интерфейс клиента биржи.

    Отдаёт только "сырую" index-цену по тикеру. Ничего не знает
    ни про БД, ни про способ сохранения, ни про транспортный
    слой FastAPI — за это отвечают другие слои.

    Timestamp цены фиксируется на стороне сервисного слоя в момент
    получения ответа (см. Design decisions).
    """

    @abstractmethod
    async def get_index_price(self, ticker: TickerEnum) -> Decimal:
        """Возвращает текущую index-цену тикера.

        Бросает `DeribitClientError`, если биржа недоступна,
        ответ невалиден или не содержит ожидаемых полей.
        """
