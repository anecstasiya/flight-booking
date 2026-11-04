# Схема данных первого этапа

```mermaid
erDiagram
    FLIGHT ||--o{ SEAT_RESERVATION : has
    FLIGHT ||..o{ BOOKING : "flight_id (logical)"
    BOOKING ||..|| SEAT_RESERVATION : "booking_id (logical)"
    FLIGHT {
        uuid id PK
        varchar flight_number
        varchar airline
        varchar origin
        varchar destination
        timestamptz departure_time
        timestamptz arrival_time
        integer total_seats
        integer available_seats
        numeric price
        varchar status
    }
    SEAT_RESERVATION {
        uuid id PK
        uuid flight_id FK
        uuid booking_id UK
        integer seat_count
        varchar status
        timestamptz created_at
    }
    BOOKING {
        uuid id PK
        varchar user_id
        uuid flight_id
        varchar passenger_name
        varchar passenger_email
        integer seat_count
        numeric total_price
        varchar status
        timestamptz created_at
    }
```

Flight и SeatReservation хранятся в flight-db, Booking — в booking-db.
Ссылки между сервисами передаются через ID, без внешних ключей между базами.

Время и дата поиска — UTC. Номер рейса уникален в пределах даты вылета UTC.
Цена хранится в рублях. total_price — стоимость на момент бронирования.
Данные пассажира относятся к конкретному бронированию.
