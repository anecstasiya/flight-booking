# Flight Booking

Python 3.12, FastAPI, gRPC, PostgreSQL, SQLAlchemy, Alembic.

Пока реализован каркас сервисов, таблицы и миграции. Поиск и бронирование
будут добавлены следующими этапами.

## Запуск

Нужен запущенный Docker с Docker Compose.

```sh
docker compose up --build
```

- REST: http://localhost:8000/health
- Swagger: http://localhost:8000/docs
- gRPC: localhost:50051, пока только Health Check.

Каждый сервис хранит данные в своей PostgreSQL. Миграции применяются
автоматически перед запуском командой `alembic upgrade head`.

Настройки по умолчанию подходят для локального запуска.
Для изменения паролей и портов скопируй `.env.example` в `.env`.
Пароли в DATABASE_URL нужно кодировать для URL; изменение `.env` не меняет
пароли в уже созданных базах.

## Проверка

```sh
sh scripts/check.sh
```

Проверяются миграции, ограничения таблиц и здоровье сервисов.
Проверочные данные откатываются. Такая же проверка запускается в GitHub Actions.

## Остановка

```sh
docker compose down
```

Данные сохраняются в Docker volumes. Схема таблиц — в [docs/schema.md](docs/schema.md).
