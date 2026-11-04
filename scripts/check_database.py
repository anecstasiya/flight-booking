import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.database import engine
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

service = sys.argv[1]
assert service in {"booking", "flight"}, "Expected booking or flight"


for _ in range(2):
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
subprocess.run([sys.executable, "-m", "alembic", "check"], check=True)

with engine.connect() as connection:
    transaction = connection.begin()
    try:
        tables = set(inspect(connection).get_table_names())
        expected = (
            {"bookings", "alembic_version"}
            if service == "booking"
            else {"flights", "seat_reservations", "alembic_version"}
        )
        assert tables == expected, (tables, expected)
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
        )

        def reject(table, values, constraint):
            from app.models import Base

            try:
                with connection.begin_nested():
                    connection.execute(Base.metadata.tables[table].insert(), values)
            except IntegrityError as error:
                assert error.orig.diag.constraint_name == constraint, str(error)
            else:
                raise AssertionError(f"Expected database constraint: {constraint}")

        if service == "booking":
            from app.models import Booking

            row = dict(
                id=uuid.uuid4(),
                user_id="migration-check",
                flight_id=uuid.uuid4(),
                passenger_name="Test Passenger",
                passenger_email="passenger@example.com",
                seat_count=1,
                total_price=Decimal("125.50"),
            )
            connection.execute(Booking.__table__.insert(), row)
            reject(
                "bookings",
                {**row, "id": uuid.uuid4(), "seat_count": 0},
                "ck_bookings_seat_count",
            )
            reject(
                "bookings",
                {**row, "id": uuid.uuid4(), "total_price": 0},
                "ck_bookings_total_price",
            )
            reject(
                "bookings",
                {**row, "id": uuid.uuid4(), "status": "UNKNOWN"},
                "ck_bookings_status",
            )
        else:
            from app.models import Flight, SeatReservation

            row = dict(
                id=uuid.uuid4(),
                flight_number=f"T{uuid.uuid4().hex[:12]}",
                airline="Test Airline",
                origin="SVO",
                destination="LED",
                departure_time=datetime(2035, 1, 1, 12, tzinfo=UTC),
                arrival_time=datetime(2035, 1, 1, 14, tzinfo=UTC),
                total_seats=10,
                available_seats=10,
                price=Decimal("125.50"),
            )
            connection.execute(Flight.__table__.insert(), row)
            for field, value, constraint in [
                ("available_seats", -1, "ck_flights_available_seats"),
                ("available_seats", 11, "ck_flights_available_seats"),
                ("total_seats", 0, "ck_flights_total_seats"),
                ("price", 0, "ck_flights_price"),
                ("origin", "sv0", "ck_flights_origin_iata"),
                ("destination", "SVO", "ck_flights_route"),
                ("status", "UNKNOWN", "ck_flights_status"),
                ("arrival_time", row["departure_time"], "ck_flights_times"),
            ]:
                candidate = {**row, "id": uuid.uuid4(), field: value}
                if field == "total_seats":
                    candidate["available_seats"] = 0
                reject("flights", candidate, constraint)

            reject(
                "flights",
                {
                    **row,
                    "id": uuid.uuid4(),
                    "departure_time": row["departure_time"] + timedelta(minutes=30),
                },
                "uq_flight_number_date",
            )
            next_day = {
                **row,
                "id": uuid.uuid4(),
                "departure_time": row["departure_time"] + timedelta(days=1),
                "arrival_time": row["arrival_time"] + timedelta(days=1),
            }
            connection.execute(Flight.__table__.insert(), next_day)

            reservation = dict(
                id=uuid.uuid4(),
                flight_id=row["id"],
                booking_id=uuid.uuid4(),
                seat_count=1,
            )
            connection.execute(SeatReservation.__table__.insert(), reservation)
            reject(
                "seat_reservations",
                {**reservation, "id": uuid.uuid4()},
                "uq_reservation_booking",
            )
            reject(
                "seat_reservations",
                {
                    **reservation,
                    "id": uuid.uuid4(),
                    "booking_id": uuid.uuid4(),
                    "seat_count": 0,
                },
                "ck_reservations_seat_count",
            )
            reject(
                "seat_reservations",
                {
                    **reservation,
                    "id": uuid.uuid4(),
                    "booking_id": uuid.uuid4(),
                    "status": "UNKNOWN",
                },
                "ck_reservations_status",
            )
    finally:
        transaction.rollback()
        engine.dispose()

print(f"{service}: migration and constraint checks passed")
