# Flight Booking

Python 3.12, FastAPI, gRPC, PostgreSQL, Redis Sentinel, SQLAlchemy и Alembic.
Booking Service хранит бронирования, Flight Service — рейсы и резервации.
У сервисов отдельные базы.

## Запуск

```sh
docker compose up --build
```

REST и Swagger: http://localhost:8000/docs. gRPC: localhost:50051.
Миграции применяются автоматически. Код gRPC генерируется из
[flight.proto](proto/contracts/flight.proto) при сборке.
[ER-диаграмма](docs/schema.md).

Для пробного рейса:

```sh
docker compose exec flight-service python -m app.seed
curl 'http://localhost:8000/flights?origin=SVO&destination=LED&date=2026-12-01'
curl -X POST http://localhost:8000/bookings -H 'Content-Type: application/json' \
  -d '{"user_id":"user-1","flight_id":"11111111-1111-4111-8111-111111111111","passenger_name":"Anna","passenger_email":"anna@example.com","seat_count":2}'
```

## API

| Метод | Назначение |
|---|---|
| GET /flights?origin=SVO&destination=LED&date=2026-12-01 | Поиск; date необязательна |
| GET /flights/{id} | Рейс |
| PATCH /flights/{id} | Изменить price или status |
| POST /bookings | Забронировать места |
| GET /bookings/{id} | Бронирование |
| GET /bookings?user_id=user-1 | Бронирования пользователя |
| POST /bookings/{id}/cancel | Отмена и возврат мест |

ID — UUID, даты — UTC, цены — десятичные строки в рублях. Статусы gRPC — enum,
время — Timestamp. Цена бронирования сохраняется на момент покупки.

Ошибки gRPC: INVALID_ARGUMENT → 400, NOT_FOUND → 404,
RESOURCE_EXHAUSTED / FAILED_PRECONDITION / ALREADY_EXISTS → 409,
UNAVAILABLE → 503, DEADLINE_EXCEEDED → 504, остальные → 502.
Невалидный REST-ввод возвращает 422. Отсутствующий или неверный gRPC API key
возвращает UNAUTHENTICATED для всех методов, включая Health Check.

## Механизмы

- Изменение мест и резервации выполняется одной транзакцией с SELECT FOR UPDATE.
  Бронирование записывается после успешного резерва; ошибка записи запускает компенсацию.
- Все gRPC-вызовы передают GRPC_API_KEY в metadata x-api-key.
- Cache-Aside: flight:{id} и search:{origin}:{destination}:{date}, TTL 600 секунд.
  UpdateFlight, ReserveSeats и ReleaseReservation очищают карточку и поиск.
  Hit/miss видны в логах. При недоступности Redis сервис читает PostgreSQL;
  при восстановлении или смене мастера старый кеш очищается.
- Redis: мастер, реплика, три Sentinel с кворумом 2. Клиент находит мастера через Sentinel.
- Retry: максимум 3 попытки, паузы 100 и 200 мс, только UNAVAILABLE и DEADLINE_EXCEEDED.
  Повтор ReserveSeats с тем же booking_id не списывает места повторно.
- Circuit Breaker реализован в клиентском interceptor: 5 ошибок за 60 секунд открывают
  цепь на 10 секунд; OPEN сразу возвращает 503; HALF_OPEN пропускает один запрос.
  Переходы CLOSED / OPEN / HALF_OPEN записываются в логи.

Настройки находятся в [.env.example](.env.example). Для изменения скопируй его в .env.
Порог, время ожидания и окно Circuit Breaker задаются CB_FAILURE_THRESHOLD,
CB_RESET_SECONDS и CB_WINDOW_SECONDS. TTL допускает 300–600 секунд.
Значения по умолчанию предназначены для локального запуска.

## Проверка

```sh
sh scripts/check.sh
```

Проверяются API, транзакции, авторизация, кеш, retry и Circuit Breaker.
Тесты также останавливают мастер Redis и Flight Service и проверяют восстановление.
Остановленные контейнеры запускаются обратно. Эти же проверки выполняет GitHub Actions.

Остановка: `docker compose down`. Данные PostgreSQL сохраняются в volumes.
