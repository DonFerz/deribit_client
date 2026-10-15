from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Декларативная база для всех ORM-моделей."""


def create_engine() -> AsyncEngine:
    """Создаёт async-engine SQLAlchemy на основе настроек."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        pool_pre_ping=True,
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику сессий, привязанную к переданному engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Возвращает единственный на процесс async-engine."""
    return create_engine()


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Возвращает единственный на процесс sessionmaker."""
    return create_sessionmaker(get_engine())


async def get_session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Отдаёт сессию и гарантирует корректное закрытие.

    Оставлено обычным async-генератором, чтобы его можно было
    обернуть в FastAPI-зависимость или использовать напрямую
    внутри Celery-задач.
    """
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
