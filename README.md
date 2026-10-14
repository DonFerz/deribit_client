deribit-client/
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── script.py.mako
│   └── README
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── celery_app.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── price.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── price.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── price_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── price_service.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── deribit_client.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── fetch_prices.py
│   └── api/
│       ├── __init__.py
│       ├── dependencies.py
│       └── v1/
│           ├── __init__.py
│           ├── router.py
│           └── prices.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_price_service.py
│   ├── test_deribit_client.py
│   └── test_price_repository.py
├── .env.example
├── .dockerignore
├── .gitignore
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── README.md
