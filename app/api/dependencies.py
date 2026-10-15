from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.repositories.uow import AbstractUnitOfWork
from app.services.price_service import PriceQueryService

UoWFactory = Callable[[], AbstractUnitOfWork]


def get_uow_factory(request: Request) -> UoWFactory:
    """Достаёт фабрику Unit of Work из состояния приложения.

    Фабрика создаётся один раз в `lifespan` и живёт всё время
    работы приложения; здесь мы лишь прокидываем её в сервис.
    """
    factory = getattr(request.app.state, "uow_factory", None)
    if factory is None:
        raise RuntimeError(
            "app.state.uow_factory is not configured. "
            "Check that lifespan sets it."
        )
    return factory


def get_price_query_service(
    uow_factory: Annotated[UoWFactory, Depends(get_uow_factory)],
) -> PriceQueryService:
    """Собирает `PriceQueryService` (read-only).

    Сервис stateless — его можно создавать на каждый запрос.
    Клиент биржи здесь не нужен: API не ходит на Deribit.
    """
    return PriceQueryService(uow_factory=uow_factory)


PriceQueryServiceDep = Annotated[
    PriceQueryService, Depends(get_price_query_service)
]
