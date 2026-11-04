# gRPC

Контракт: `contracts/flight.proto`. Код генерируется через grpc_tools.protoc
при сборке каждого контейнера. Сгенерированные файлы исключены из Git.

| Метод | Запрос | Результат |
|---|---|---|
| SearchFlights | origin, destination, необязательная date | Рейсы со статусом SCHEDULED |
| GetFlight | flight_id | Информация о рейсе |
| ReserveSeats | flight_id, seat_count, booking_id | Резервация мест |
| ReleaseReservation | booking_id | Освобождённая резервация |

ID передаются как UUID-строки. Время и дата поиска — Timestamp в UTC.
Для поиска используется календарная дата UTC из Timestamp; отсутствие date
означает поиск по всем датам. Цена передаётся десятичной строкой в рублях.
Статусы определены через enum.

| Ошибка | Когда возвращается | HTTP |
|---|---|---|
| INVALID_ARGUMENT | Невалидный UUID, IATA-код, дата или количество мест | 400 |
| NOT_FOUND | Рейс или резервация не найдены | 404 |
| RESOURCE_EXHAUSTED | Недостаточно мест | 409 |
| FAILED_PRECONDITION | Рейс не SCHEDULED или резервация больше не активна | 409 |
| ALREADY_EXISTS | booking_id использован с другими параметрами | 409 |
| UNAVAILABLE | Flight Service недоступен | 503 |
| DEADLINE_EXCEEDED | Превышено время ожидания | 504 |

Невалидные REST-запросы отклоняются FastAPI с HTTP 422 до вызова gRPC.
Остальные ошибки gRPC преобразуются в HTTP 502.

Повторное ReserveSeats с тем же booking_id и параметрами возвращает активную
резервацию. Повторное ReleaseReservation не возвращает места второй раз.

Локальная генерация после установки requirements-dev.txt:

```sh
python scripts/generate_proto.py proto booking-service
python scripts/generate_proto.py proto flight-service
```
