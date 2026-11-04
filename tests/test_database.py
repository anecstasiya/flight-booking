import psycopg
import pytest
from test_booking import booking_body


@pytest.mark.parametrize(
    "field,value",
    [
        ("available_seats", -1),
        ("available_seats", 5),
        ("total_seats", 0),
        ("price", 0),
        ("origin", "bad"),
        ("destination", "SVO"),
        ("status", "BAD"),
    ],
)
def test_flight_constraints(new_flight, flight_db, field, value):
    flight = new_flight()
    with pytest.raises(psycopg.errors.CheckViolation):
        flight_db.execute(
            psycopg.sql.SQL("UPDATE flights SET {} = %s WHERE id = %s").format(
                psycopg.sql.Identifier(field)
            ),
            [value, flight["id"]],
        )


@pytest.mark.parametrize(
    "field,value", [("seat_count", 0), ("total_price", 0), ("status", "BAD")]
)
def test_booking_constraints(api, new_flight, booking_db, field, value):
    flight = new_flight()
    booking = api.post("/bookings", json=booking_body(flight)).json()
    with pytest.raises(psycopg.errors.CheckViolation):
        booking_db.execute(
            psycopg.sql.SQL("UPDATE bookings SET {} = %s WHERE id = %s").format(
                psycopg.sql.Identifier(field)
            ),
            [value, booking["id"]],
        )


def test_flight_number_date_is_unique(new_flight):
    flight = new_flight()
    with pytest.raises(psycopg.errors.UniqueViolation):
        new_flight(flight_number=flight["flight_number"])
