# Flight Booking

Учебная система бронирования авиабилетов на Python 3.12.
Работа идёт небольшими этапами: реализация → проверка → коммит → push.

## Текущий этап

Готов каркас двух сервисов, две отдельные PostgreSQL, первые миграции
Alembic, проверки здоровья и сценарий проверки схемы. Бизнес-методы поиска,
бронирования и отмены будут добавлены следующими коммитами. Redis появится
на этапе кеширования.

| Компонент | Назначение | Технологии |
|---|---|---|
| Booking Service | REST API и бронирования | FastAPI, SQLAlchemy, Alembic |
| Flight Service | gRPC API, рейсы и резервации | grpcio, SQLAlchemy, Alembic |
| booking-db | Только данные Booking Service | PostgreSQL 17 |
| flight-db | Только данные Flight Service | PostgreSQL 17 |

## Запуск

Нужен установленный и запущенный Docker с Docker Compose v2.
Локальный Python для запуска через Docker не нужен.

Из корня репозитория:

```sh
docker compose up --build
```

Compose дождётся готовности баз. Каждый сервис автоматически применит свои
миграции командой `alembic upgrade head`, затем запустит приложение.
Если миграция завершится ошибкой, приложение не запустится.

После запуска:

- REST-проверка: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs
- gRPC: `localhost:50051` — пока только стандартный Health Check.

Проверка REST:

```sh
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok","service":"booking-service"}
```

Статус контейнеров и логи миграций:

```sh
docker compose ps
docker compose logs booking-service flight-service
```

Остановка с сохранением данных:

```sh
docker compose down
```

PostgreSQL хранит данные в двух отдельных Docker volumes. Порты баз наружу
не опубликованы; порт REST и порт gRPC доступны только на этом компьютере.

## Настройки

Для первого учебного запуска достаточно значений по умолчанию.
Чтобы изменить пароли или порты:

```sh
cp .env.example .env
```

Отредактируй `.env` до первого запуска. Этот файл исключён из Git.
Пароли по умолчанию предназначены для локальной разработки.
В паролях, подставляемых в DATABASE_URL, специальные символы нужно кодировать
для URL. Уже созданный PostgreSQL volume сохраняет прежний пароль:
изменение `.env` само по себе пароль существующего пользователя БД не меняет.

## Что такое миграции

Миграция — версия изменения структуры базы, сохранённая в Python-файле.
В первой миграции `0001_initial.py` создаются таблицы:

- Booking Service: `bookings`;
- Flight Service: `flights`, `seat_reservations`.

У каждого сервиса отдельная папка `migrations/` и своя таблица
`alembic_version` в собственной базе. Alembic хранит в этой таблице текущую
версию схемы. Поэтому повторный `upgrade head` пропускает уже применённые
миграции и сохраняет существующие данные.

В файле миграции:

- `upgrade()` применяет изменение;
- `downgrade()` описывает его отмену. Откат с удалением таблиц удалит и их данные.

Как добавить следующее изменение:

1. Изменить модель в `booking-service/app/models.py` или `flight-service/app/models.py`.
2. Пересобрать соответствующий контейнер, чтобы в нём была новая модель:

   ```sh
   docker compose up -d --build booking-service
   ```

3. Создать миграцию в контейнере и скопировать её в репозиторий:

   ```sh
   docker compose exec booking-service alembic revision --autogenerate -m add_booking_field
   docker compose cp booking-service:/app/migrations/versions/. booking-service/migrations/versions/
   ```

4. Проверить сгенерированный файл вручную: autogenerate предлагает изменения,
   но не гарантирует правильного распознавания переименований и всех ограничений.
5. Пересобрать сервис ещё раз. При старте новая миграция применится автоматически:

   ```sh
   docker compose up -d --build booking-service
   ```

6. Запустить проверки, затем закоммитить модель вместе с миграцией.

Для Flight Service используй те же команды с `flight-service`.
Применённые миграции не переписываем: для изменения схемы создаём следующий файл.

## Проверки

```sh
sh scripts/check.sh
```

Сценарий поднимает контейнеры, проверяет обе базы, повторное применение
миграций, соответствие схемы моделям, ограничения данных и здоровье сервисов.
Проверочные записи откатываются; таблицы и реальные данные сохраняются.
После проверки контейнеры остаются запущенными.

В `.github/workflows/ci.yml` подготовлена такая же проверка для каждого push
и pull request в GitHub, а также проверка Python через Ruff.

## Структура

```text
booking-service/       REST-сервис, модели и его миграции
flight-service/        gRPC-сервис, модели и его миграции
proto/                 место для собственного gRPC-контракта
docs/schema.md         ER-диаграмма и решения по данным
scripts/               проверки запуска и схемы
docker-compose.yml     запуск сервисов и баз
```

## Следующие этапы

1. Спроектировать `flight.proto` и подключить генерацию кода.
2. Реализовать поиск и получение рейсов.
3. Реализовать создание, получение, список и отмену бронирований.
4. Добавить транзакции и проверку конкурентного резервирования.
5. Добавить аутентификацию gRPC.
6. Добавить Redis, TTL и инвалидацию кеша.
7. Добавить retry, идемпотентность, Redis Sentinel и Circuit Breaker.

## Документация

- [Миграции Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Порядок запуска в Compose](https://docs.docker.com/compose/how-tos/startup-order/)
- [gRPC на Python](https://grpc.io/docs/languages/python/basics/)
