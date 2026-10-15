from datetime import timedelta

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from app.core.config import get_settings
from app.core.logging import setup_logging

FETCH_INDEX_PRICES_TASK = "app.tasks.fetch_prices.fetch_index_prices"


@celery_setup_logging.connect
def _configure_celery_logging(**kwargs: object) -> None:
    """Переопределяем логирование Celery на наше."""
    setup_logging()


def create_celery_app() -> Celery:
    """Создаёт и настраивает Celery-приложение."""
    settings = get_settings()

    app = Celery(
        "deribit-client",
        broker=settings.redis_url,
        include=["app.tasks.fetch_prices"],
    )

    app.conf.update(
        broker_connection_retry_on_startup=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=30,
        task_time_limit=60,
        beat_schedule={
            "fetch-index-prices": {
                "task": FETCH_INDEX_PRICES_TASK,
                "schedule": timedelta(seconds=settings.celery_fetch_interval_seconds),
            },
        },
    )

    return app


celery_app = create_celery_app()
