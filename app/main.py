from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import v1_router
from app.core.config import get_settings
from app.core.database import create_engine, create_sessionmaker
from app.core.exceptions import (
    DeribitClientError,
    DomainError,
    InvalidDateRangeError,
    PriceNotFoundError,
)
from app.core.logging import get_logger, setup_logging
from app.repositories.uow import SQLAlchemyUnitOfWork

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управляет жизненным циклом общих ресурсов приложения.

    Создаёт и кладёт в `app.state` фабрику Unit of Work. Клиент
    Deribit в API не нужен — он используется только в Celery-задаче.
    """
    engine = create_engine()
    try:
        sessionmaker = create_sessionmaker(engine)

        def uow_factory() -> SQLAlchemyUnitOfWork:
            return SQLAlchemyUnitOfWork(sessionmaker)

        app.state.uow_factory = uow_factory

        logger.info("Application started")
        yield
        logger.info("Application stopped")
    finally:
        await engine.dispose()


def _register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует маппинг доменных исключений в HTTP-ответы.

    Слой API — единственное место, где доменные исключения
    превращаются в HTTP-статусы. Сервис и репозитории про
    HTTP ничего не знают.
    """

    @app.exception_handler(PriceNotFoundError)
    async def _handle_price_not_found(
        _: Request, exc: PriceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidDateRangeError)
    async def _handle_invalid_range(
        _: Request, exc: InvalidDateRangeError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DeribitClientError)
    async def _handle_deribit_error(
        _: Request, exc: DeribitClientError
    ) -> JSONResponse:
        # 502 — «вышестоящий сервис (Deribit) ответил некорректно».
        # Сюда мы не должны попадать из API (клиент вызывается
        # только из Celery), но оставляем как страховку.
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _handle_domain_fallback(
        _: Request, exc: DomainError
    ) -> JSONResponse:
        # Страховка: если появится новое доменное исключение
        # и про него забудут — вернём 400, а не 500.
        return JSONResponse(status_code=400, content={"detail": str(exc)})


def create_app() -> FastAPI:
    """Фабрика FastAPI-приложения.

    Используется uvicorn-ом с флагом `--factory`:
        uvicorn app.main:create_app --factory

    Никаких модульных инстансов `app = FastAPI(...)` — это
    упрощает тесты (каждый тест может собрать свой app) и не
    создаёт «глобальную переменную».
    """
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Сервис сбора index-цен btc_usd / eth_usd с биржи Deribit "
            "и предоставления их через REST API."
        ),
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    app.include_router(v1_router)
    _register_exception_handlers(app)
    return app
