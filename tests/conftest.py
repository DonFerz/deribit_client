from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.models import Price  # noqa: F401
from app.core.database import Base
from app.main import create_app
from app.repositories.uow import SQLAlchemyUnitOfWork

__all__ = ["Price"]


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """In-memory SQLite с StaticPool на каждый тест.

    StaticPool нужен, потому что SQLite `:memory:` создаёт свою БД
    на каждое соединение. С StaticPool все сессии идут через одно
    соединение и видят одни и те же таблицы.

    Postgres-специфичные типы (`Numeric(18, 8)`, `BigInteger`) в
    SQLite работают: `Numeric` → `NUMERIC`, `BigInteger` → `INTEGER`
    (SQLite не различает размеры целых).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def sessionmaker(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий, привязанная к in-memory SQLite."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
def uow_factory(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Callable[[], SQLAlchemyUnitOfWork]:
    """Фабрика UoW для сервисов и API-тестов."""
    return lambda: SQLAlchemyUnitOfWork(sessionmaker)


@pytest.fixture
async def test_app(
    uow_factory: Callable[[], SQLAlchemyUnitOfWork],
) -> AsyncIterator[FastAPI]:
    """FastAPI-приложение с подменённой UoW-фабрикой.

    `lifespan` не запускаем: в нём создаются Postgres-engine и
    aiohttp-сессия, которые для тестов API не нужны. Вместо этого
    кладём UoW-фабрику в `app.state` руками — этого достаточно,
    потому что DI достаёт её оттуда через `getattr`.
    """
    application = create_app()
    application.state.uow_factory = uow_factory
    yield application


@pytest.fixture
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент к тестовому приложению поверх ASGI-транспорта.

    ASGITransport работает быстрее реального HTTP: запрос сразу
    уходит в приложение, без сокетов и сети.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        yield http_client
