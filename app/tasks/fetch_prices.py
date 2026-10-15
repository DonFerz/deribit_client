from __future__ import annotations

import asyncio

import aiohttp
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.clients.deribit_client import DeribitClient
from app.core.celery_app import FETCH_INDEX_PRICES_TASK, celery_app
from app.core.config import get_settings
from app.core.database import create_task_engine
from app.core.logging import get_logger
from app.repositories.uow import SQLAlchemyUnitOfWork
from app.schemas.price import TickerEnum
from app.services.price_service import PriceCollectorService

logger = get_logger(__name__)


@celery_app.task(name=FETCH_INDEX_PRICES_TASK)
def fetch_index_prices() -> list[str]:
    """Периодическая задача сбора index-цен btc_usd/eth_usd с Deribit.

    Запускается Celery beat каждые `CELERY_FETCH_INTERVAL_SECONDS`
    секунд. Внутри создаёт собственный event loop через
    `asyncio.run` — поэтому все зависимости (engine, session,
    aiohttp-сессия) создаются локально и уничтожаются в конце
    вызова. Никакого состояния между запусками не сохраняется.
    """
    try:
        stored = asyncio.run(_collect_and_store_prices())
    except Exception:
        logger.exception("Celery-задача fetch_index_prices упала")
        raise

    return [ticker.value for ticker in stored]


async def _collect_and_store_prices() -> list[TickerEnum]:
    """Асинхронная часть задачи: собирает и сохраняет цены.

    Порядок создания зависимостей — «снизу вверх»:
    engine → sessionmaker → UoW-фабрика → клиент → сервис.

    Клиент использует один aiohttp.ClientSession на весь батч —
    это эффективнее, чем открывать сессию на каждый тикер.
    """
    settings = get_settings()
    tickers = _parse_tickers(settings.deribit_tickers)

    engine = create_task_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(sessionmaker)

    try:
        async with aiohttp.ClientSession() as session:
            client = DeribitClient.from_settings(session)
            service = PriceCollectorService(uow_factory=uow_factory, client=client)
            return await service.collect_and_store(tickers)
    finally:
        await engine.dispose()


def _parse_tickers(raw_tickers: list[str]) -> list[TickerEnum]:
    """Приводит строки из настроек к `TickerEnum`.

    Невалидные значения молча отбрасываются с предупреждением —
    чтобы опечатка в конфиге не валила всю задачу целиком.
    """
    parsed: list[TickerEnum] = []
    for raw in raw_tickers:
        try:
            parsed.append(TickerEnum(raw))
        except ValueError:
            logger.warning(
                "Неизвестный тикер в настройках — пропускаем",
                extra={"ticker": raw},
            )

    if not parsed:
        raise RuntimeError("Не задан ни один валидный тикер для сбора цен")

    return parsed
