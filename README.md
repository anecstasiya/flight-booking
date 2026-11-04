# Flight Booking

Python 3.12, FastAPI, gRPC, PostgreSQL, SQLAlchemy, Alembic.

Реализован первый блок задания: поиск рейсов, создание, просмотр и отмена
бронирований. Booking Service вызывает Flight Service по gRPC.

## Запуск

Нужен запущенный Docker с Docker Compose.

```sh
docker compose up --build
```

- REST: http://localhost:8000/health
- Swagger: http://localhost:8000/docs
- gRPC: localhost:50051.

Каждый сервис хранит данные в своей PostgreSQL. Миграции применяются
автоматически перед запуском командой `alembic upgrade head`.

Настройки по умолчанию подходят для локального запуска.
Для изменения паролей и портов скопируй `.env.example` в `.env`.
Пароли в DATABASE_URL нужно кодировать для URL; изменение `.env` не меняет
пароли в уже созданных базах.

## Пример

Добавить демонстрационный рейс:

```sh
docker compose exec flight-service python -m app.seed
curl 'http://localhost:8000/flights?origin=SVO&destination=LED&date=2026-12-01'
```

Забронировать два места:

```sh
curl -X POST http://localhost:8000/bookings \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-1","flight_id":"11111111-1111-4111-8111-111111111111","passenger_name":"Anna","passenger_email":"anna@example.com","seat_count":2}'
```

Ответ содержит id бронирования, статус CONFIRMED и total_price = 10000.00.
Для отмены подставь полученный id:

```sh
curl -X POST http://localhost:8000/bookings/BOOKING_ID/cancel
```

| REST | Назначение |
|---|---|
| GET /flights?origin=SVO&destination=LED&date=2026-12-01 | Поиск; date необязательна |
| GET /flights/{id} | Получение рейса |
| POST /bookings | Создание бронирования |
| GET /bookings/{id} | Получение бронирования |
| GET /bookings?user_id=user-1 | Список бронирований пользователя |
| POST /bookings/{id}/cancel | Отмена бронирования и возврат мест |

Цены передаются десятичными строками. Время и дата поиска — UTC.
Недостаток мест и повторная отмена возвращают 409, отсутствие записи — 404.
Некорректный ввод возвращает 422. Если Flight Service недоступен, ответ — 503.
Бронирование создаётся после GetFlight и успешного ReserveSeats.
При ошибке сохранения Booking Service пытается освободить резервацию.
Полное восстановление после потери связи между сервисами потребует отдельного
механизма согласования; в первом блоке его нет.

gRPC-контракт и коды ошибок — в [proto/README.md](proto/README.md).

## Проверка

```sh
sh scripts/check.sh
```

Проверяются миграции, ограничения таблиц, REST, gRPC и конкурентное бронирование
последнего места. Тестовый контейнер запускается только с профилем test.
Проверочные записи удаляются после тестов. Такая же проверка запускается
в GitHub Actions.

## Остановка

```sh
docker compose down
```

Данные сохраняются в Docker volumes. Схема таблиц — в [docs/schema.md](docs/schema.md).
