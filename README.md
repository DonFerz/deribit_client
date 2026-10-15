# deribit-client

Сервис периодического сбора index-цен `btc_usd` и `eth_usd` с биржи
[Deribit](https://docs.deribit.com/) и предоставления их через REST API.

Каждую минуту Celery-задача забирает у Deribit текущие index-цены,
сохраняет тикер, цену и UNIX-timestamp в PostgreSQL. FastAPI отдаёт
сохранённые данные через три GET-эндпоинта.

---

## Стек

| Слой | Технология |
|---|---|
| Язык | Python 3.12 |
| Web | FastAPI + Uvicorn |
| БД | PostgreSQL 16 + SQLAlchemy 2.0 (async) + asyncpg |
| Миграции | Alembic |
| Очереди | Celery 5 + Redis |
| HTTP-клиент | aiohttp |
| Конфиг | pydantic-settings |
| Тесты | pytest + pytest-asyncio + aioresponses + httpx |
| Инфраструктура | Docker + Docker Compose |

---

## Быстрый старт (Docker)

Требуется только Docker Desktop.

```bash
git clone <repo-url> deribit-client
cd deribit-client
cp .env.example .env       # при необходимости поправь порты
docker compose up --build -d
```

Поднимаются пять сервисов:

| Сервис | Роль | Порт на хосте |
|---|---|---|
| `db` | PostgreSQL | `127.0.0.1:5433` |
| `redis` | Брокер Celery | внутри сети |
| `migrate` | one-shot `alembic upgrade head` | — |
| `api` | FastAPI (Uvicorn) | `127.0.0.1:8001` |
| `worker` | Celery worker + beat | — |

Первый запуск собирает образ (~2–3 минуты). Дальше — секунды.

Проверка:

```bash
curl http://localhost:8001/health
# {"status":"ok"}

# данные появятся через ~60 секунд после старта worker'а
curl "http://localhost:8001/api/v1/prices/latest?ticker=btc_usd"
```

Swagger UI: <http://localhost:8001/docs>

Логи:

```bash
docker compose logs -f api
docker compose logs -f worker
```

Остановка:

```bash
docker compose down        # сохраняет данные в volume
docker compose down -v     # удаляет volume с БД
```

---

## Локальный запуск (без Docker)

Понадобятся поднятые PostgreSQL и Redis. Удобно через контейнеры:

```bash
docker run -d --name deribit-pg \
  -e POSTGRES_USER=deribit -e POSTGRES_PASSWORD=deribit \
  -e POSTGRES_DB=deribit -p 5433:5432 postgres:16-alpine

docker run -d --name deribit-redis \
  -p 6379:6379 redis:7-alpine
```

Далее:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements-dev.txt

cp .env.example .env            # POSTGRES_PORT=5433, REDIS_HOST=localhost

alembic upgrade head

# три терминала:
uvicorn app.main:create_app --factory --port 8001
celery -A app.core.celery_app:celery_app worker -B --loglevel=info
```

---

## API

Базовый префикс — `/api/v1`. У всех методов обязательный query-параметр
`ticker` со значениями `btc_usd` или `eth_usd`. Timestamp — UNIX-время
в **миллисекундах UTC**. Цена — строка (Pydantic сериализует `Decimal`
строкой, чтобы не терять точность).

### `GET /health`

Проверка живости. Используется Docker healthcheck'ом.

```json
{"status": "ok"}
```

### `GET /api/v1/prices/all?ticker=btc_usd`

Все сохранённые цены тикера, сортировка по возрастанию timestamp.

```bash
curl "http://localhost:8001/api/v1/prices/all?ticker=btc_usd"
```

```json
{
  "ticker": "btc_usd",
  "prices": [
    {"ticker": "btc_usd", "price": "82383.46", "timestamp": 1792103584055},
    {"ticker": "btc_usd", "price": "82401.11", "timestamp": 1792103644081}
  ]
}
```

Пустой список — валидный ответ (200).

### `GET /api/v1/prices/latest?ticker=btc_usd`

Последняя сохранённая цена тикера.

```json
{
  "ticker": "btc_usd",
  "price": "82383.46",
  "timestamp": 1792103584055
}
```

Если данных ещё нет — **404** с `{"detail": "No prices found for ticker 'btc_usd'"}`.

### `GET /api/v1/prices/by-period?ticker=btc_usd&from=...&to=...`

Цены в заданном диапазоне. Границы `from` / `to` — включительные,
формат ISO 8601 (UTC, `AwareDatetime`). Обе границы опциональны:
без `from` — «с начала времён», без `to` — «до текущего момента».

```bash
curl "http://localhost:8001/api/v1/prices/by-period?ticker=btc_usd&from=2025-01-01T00:00:00Z&to=2025-01-02T00:00:00Z"
```

Если `from > to` — **400**.

Полная OpenAPI-схема: `/openapi.json`, интерактивный Swagger: `/docs`.

---

## Тесты

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Покрытие:

| Файл | Что проверяет |
|---|---|
| `test_price_repository.py` | CRUD-контракт репозитория на in-memory SQLite |
| `test_price_service.py` | `PriceQueryService` и `PriceCollectorService`, включая partial-success и границы диапазона |
| `test_deribit_client.py` | Happy path, HTTP-ошибки, таймаут, битый JSON, точность `Decimal` |
| `test_api.py` | Все эндпоинты, включая 404, 400 и 422 |

В Docker:

```bash
docker compose run --rm api pytest tests/ -v
```

---

## Структура проекта

```
deribit-client/
├── alembic/                        # миграции Alembic (async env.py)
├── app/
│   ├── main.py                     # фабрика FastAPI + lifespan + exception handlers
│   ├── core/
│   │   ├── config.py               # pydantic-settings, Settings / get_settings
│   │   ├── database.py             # Base, engine/sessionmaker-фабрики
│   │   ├── celery_app.py           # Celery app + beat_schedule
│   │   ├── exceptions.py           # доменные исключения
│   │   ├── logging.py              # настройка логов
│   │   └── time.py                 # datetime ↔ unix ms
│   ├── models/price.py             # ORM-модель Price
│   ├── schemas/price.py            # Pydantic-схемы + TickerEnum
│   ├── repositories/
│   │   ├── base.py                 # AbstractPriceRepository
│   │   ├── price_repository.py     # SQLAlchemy-реализация
│   │   └── uow.py                  # Unit of Work (интерфейс + реализация)
│   ├── services/price_service.py   # PriceQueryService + PriceCollectorService
│   ├── clients/
│   │   ├── base.py                 # AbstractPriceClient
│   │   └── deribit_client.py       # aiohttp-реализация
│   ├── tasks/fetch_prices.py       # Celery-задача каждые 60 секунд
│   └── api/
│       ├── dependencies.py         # DI-провайдеры
│       ├── health.py               # GET /health
│       └── v1/
│           ├── router.py           # агрегатор /api/v1
│           └── prices.py           # три GET-эндпоинта
├── tests/                          # pytest
├── Dockerfile                      # один образ для api / worker / migrate
├── docker-compose.yml              # db, redis, migrate, api, worker
├── requirements.txt                # runtime-зависимости
├── requirements-dev.txt            # + тесты и линтеры
├── alembic.ini
└── .env.example
```

---

## Design decisions

### 1. Async везде

FastAPI, SQLAlchemy (asyncpg) и aiohttp — всё асинхронное. Это даёт
максимум при 60-секундной периодичности задач и умеренном RPS:
один воркер Uvicorn может обрабатывать много запросов параллельно,
а Celery-задача не блокирует процесс на время HTTP-запроса.

### 2. Слои и направление зависимостей

```
api  →  services  →  repositories  →  models
                ↘
                clients (aiohttp)
```

- **`api`** знает про HTTP и только маппит доменные исключения в коды.
- **`services`** — единственное место с бизнес-логикой. Ни HTTP, ни SQL, ни aiohttp.
- **`repositories`** работают только с БД и примитивами (int, Decimal).
- **`clients`** — тонкий HTTP-клиент биржи, stateless по данным.

Никакой слой не «протекает» в соседний. Например, `PriceQueryService`
не подозревает, что у нас есть Deribit, а `DeribitClient` не знает про БД.

### 3. Unit of Work для границ транзакции

Репозиторий делает `flush()`, но не `commit()`. Границей транзакции
управляет UoW:

```python
async with self._uow_factory() as uow:
    await uow.prices.add(...)
    await uow.prices.add(...)
    # commit на выходе, rollback при исключении
```

**Почему так:**
- Сервис не может «забыть» закоммитить — это делает `__aexit__`.
- Один батч = одна транзакция: если запись второго тикера падает, первый тоже откатывается.
- UoW за интерфейсом (`AbstractUnitOfWork`) — в тестах легко подменить реализацию.

### 4. Разделение `PriceQueryService` / `PriceCollectorService`

Изначально был один `PriceService` с клиентом биржи в конструкторе. Но
API не ходит на Deribit — значит, требовать от него клиента неправильно
(нарушение Interface Segregation Principle). Разделили на два класса:

- `PriceQueryService(uow_factory)` — только чтение.
- `PriceCollectorService(uow_factory, client)` — сбор + запись, используется Celery-задачей.

DI-граф стал честным: API не требует того, чего у него нет, тесты
не мокают лишнее.

### 5. Один timestamp на батч

`collect_and_store` фиксирует `now_ms = now_unix_ms()` **до** запросов
к бирже и использует его для всех тикеров. Это даёт «точку сбора»:
две цены, снятые в одном цикле, имеют одинаковый timestamp, и их можно
отличить от следующего цикла.

Если бы мы считали время после каждого HTTP-ответа, два тикера
получили бы разные timestamp — это создало бы «шум» при анализе.

### 6. Цены — `Decimal` + `Numeric(18, 8)`

Float для финансовых данных неприемлем: `0.1 + 0.2 != 0.3`. В БД — `Numeric(18, 8)`,
в Python — `Decimal`, в JSON — строка (Pydantic сериализует Decimal как строку).

При парсинге ответа Deribit: `Decimal(str(raw_price))`. Deribit присылает
`index_price` как JSON-число (float на стороне сервера), и без промежуточного
`str()` получили бы длинный хвост из двоичного представления float.

### 7. Timestamp — миллисекунды UTC

Единая единица по всему проекту: модель, схемы, репозиторий, API.
Миллисекунды удобнее секунд для фронта (`new Date(ms)` работает из коробки)
и точнее для крипто-данных, где цена может меняться внутри секунды.

### 8. Уникальный `(ticker, timestamp)` вместо отдельного индекса

`UniqueConstraint("ticker", "timestamp")` в Postgres создаёт implicit b-tree
индекс на эту пару. Он же используется запросами «все цены по тикеру» и
«последняя цена» — отдельный индекс не нужен.

Constraint защищает от дубликатов при повторной доставке Celery-задачи
(`task_acks_late=True`): если воркер упал после записи, но до ack, задача
повторится и получит `IntegrityError` — это лучше, чем молчаливое дублирование.

### 9. `NullPool` в Celery и почему нельзя переиспользовать engine

`asyncio.run()` создаёт новый event loop при каждом вызове. Пул asyncpg
привязан к loop'у, в котором создан. Если переиспользовать закэшированный
в `lru_cache` engine между вызовами таска, получим:

```
RuntimeError: got Future attached to a different loop
```

Поэтому для Celery используем `create_task_engine()` с `poolclass=NullPool`:
каждое соединение открывается и закрывается само, привязки к loop'у нет.
Раз в минуту это не бьёт по производительности.

В FastAPI пул остаётся — там один долгоживущий loop.

### 10. Фабрика `create_app()` вместо `app = FastAPI()`

Модульный синглтон `app` — это глобальная переменная. Мы используем
фабрику, uvicorn запускает `app.main:create_app --factory`. Плюсы:

- В тестах можно собрать приложение с другими настройками.
- Нет глобального мутабельного состояния на уровне импорта.
- Легче читать `lifespan`: явно видно, что создаётся и когда убирается.

### 11. Долгоживущие ресурсы в `lifespan`

`engine`, `sessionmaker` и `aiohttp.ClientSession` создаются один раз
при старте и живут до остановки. `aiohttp`-сессия переиспользует
TCP-соединения — открывать её на каждый запрос расточительно.
В `app.state` кладём UoW-фабрику, DI достаёт её через `Request`.

### 12. Кэшированные фабрики, а не глобальные инстансы

`get_settings()`, `get_engine()`, `get_sessionmaker()` — функции с `@lru_cache`.
Это не «глобальные переменные», а ленивые фабрики:

- в тестах легко сбросить кэш (`get_settings.cache_clear()`);
- приложение не читает ENV на импорте модуля;
- можно переопределить через FastAPI `dependency_overrides`.

### 13. `-B` в Celery worker для тестового, отдельный beat для прода

Сейчас beat запускается в одном процессе с worker'ом (`celery worker -B`).
Это компромисс для тестового задания: два контейнера вместо трёх.

**В проде так нельзя:** при масштабировании воркера каждая реплика запустит
свой beat, задачи будут дублироваться. Правильно — отдельный сервис
`celery beat` в единственном экземпляре. В README зафиксировано, что
это осознанное упрощение.

### 14. Внутренний порт контейнера ≠ внешний порт на хосте

В `Dockerfile` uvicorn всегда слушает **8000** — это деталь образа, она
не должна зависеть от `.env`. Compose маппит внешний `APP_PORT`
(например, `8001`) на внутренний `8000`. Так конфликт с другим проектом
на хосте решается одной переменной, а не пересборкой образа.

### 15. Один образ, три команды

`api`, `worker` и `migrate` используют один и тот же образ, отличаются
только `command` в compose. Меньше дублирования в `Dockerfile`, единый
набор зависимостей, проще пересобирать.

`migrate` — отдельный one-shot сервис (`restart: "no"`). Не вешаем
`alembic upgrade head` в команду API: при двух репликах API миграции
погнали бы наперегонки.

### 16. Health-checks для надёжного старта

`db` и `redis` имеют healthcheck (`pg_isready`, `redis-cli ping`).
`migrate` зависит от них через `condition: service_healthy` — ждёт
**готовности**, а не просто запуска контейнера. Без этого Alembic
мог стартовать раньше Postgres и упасть с `connection refused`.

`api` тоже healthcheck — через `urllib.request` из stdlib, потому что
в `python:3.12-slim` нет `curl`, и ставить его ради одной проверки
не хочется.

### 17. Доменные исключения вместо HTTP в сервисах

Сервисы кидают `PriceNotFoundError`, `InvalidDateRangeError`, `DeribitClientError`.
Маппинг в HTTP-коды — в одном месте (`main.py`):

| Исключение | HTTP |
|---|---|
| `PriceNotFoundError` | 404 |
| `InvalidDateRangeError` | 400 |
| `TickerNotFoundError` | 400 |
| `DeribitClientError` | 502 |
| Любой другой `DomainError` | 400 (fallback) |

Сервис не знает про HTTP. Если мы решим отдавать данные не через FastAPI
(CLI, gRPC), сервис останется неизменным.

---

## Возможные улучшения

Что бы я добавил при выходе за рамки тестового:

1. **Retry для Celery-задачи** с экспоненциальным backoff'ом, но только
   для сетевых ошибок (`aiohttp.ClientError`), чтобы не долбить Deribit
   при 5xx.
2. **Метрики Prometheus** — счётчик собранных цен, латентность запросов
   к Deribit, количество ошибок.
3. **Rate limiting** на API — `slowapi` или nginx.
4. **Отдельный сервис `beat`** вместо `-B` в worker'е.
5. **Pagination для `/prices/all`** — при больших объёмах данных
   возвращать всё неразумно. Сейчас это ок для тестового.
6. **Аутентификация** на API — API-key или JWT.
7. **Структурированные логи в JSON** — `structlog` или
   `python-json-logger`, чтобы Loki/ELK парсили без regexp.
8. **Alembic autogenerate в CI** — проверка, что модель и миграции
   синхронны (`alembic check`).
9. **Health-check с проверкой БД и Redis** — сейчас `/health` только
   про процесс, что осознанно (см. комментарий в `app/api/health.py`).

---

## Лицензия

Тестовое задание, распространяется как есть.
