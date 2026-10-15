from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Ответ healthcheck-эндпоинта."""

    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка живости сервиса",
    include_in_schema=True,
)
async def health() -> HealthResponse:
    """Отдаёт `{"status": "ok"}`, если приложение поднялось.

    Используется Docker healthcheck'ом и (в проде) балансировщиком.
    Никаких проверок БД/Redis здесь нет: эндпоинт отвечает за
    «процесс жив и принимает HTTP», а не за «все зависимости здоровы».
    """
    return HealthResponse(status="ok")
