from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.base import AbstractPriceRepository
from app.repositories.price_repository import SQLAlchemyPriceRepository


class AbstractUnitOfWork(ABC):
    """Абстрактная единица работы (Unit of Work).

    Инкапсулирует границы транзакции и набор репозиториев,
    доступных в рамках одной бизнес-операции.

    Контракт использования:

        async with uow_factory() as uow:
            await uow.prices.add(...)
            # commit произойдёт автоматически на выходе
            # без исключения; rollback — при исключении.

    Сервисный слой зависит только от этого интерфейса.
    """

    prices: AbstractPriceRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class SQLAlchemyUnitOfWork(AbstractUnitOfWork):
    """Реализация Unit of Work поверх SQLAlchemy 2.0 (async)."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._sessionmaker()
        self.prices = SQLAlchemyPriceRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None:
                await session.rollback()
            else:
                await session.commit()
        except Exception:
            # commit упал — пытаемся откатить. Если и rollback
            # падает — не маскируем исходную ошибку.
            try:
                await session.rollback()
            except Exception:
                # Логирование — на уровне вызывающего.
                pass
            raise
        finally:
            await session.close()
            self._session = None

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork is not initialized. "
                "Use 'async with uow:' before accessing the session."
            )
        return self._session
