FROM python:3.12-slim

# Отключаем .pyc, включаем unbuffered stdout для Docker-логов.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

RUN useradd --create-home --shell /bin/bash --uid 1000 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Внутри контейнера — всегда 8000. Наружу compose маппит его
# на APP_PORT (или 8000 по умолчанию). Внутренний порт не должен
# зависеть от .env: это деталь образа, а не конфигурации.
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]

