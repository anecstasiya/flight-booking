import os
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from uuid import uuid4

import grpc
import httpx
import psycopg
import pytest
from contracts import flight_pb2_grpc
from redis.sentinel import Sentinel


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=os.environ["BOOKING_URL"], timeout=10) as client:
        yield client


@pytest.fixture(scope="session")
def stub():
    with grpc.insecure_channel(os.environ["FLIGHT_SERVICE_ADDRESS"]) as channel:
        client = flight_pb2_grpc.FlightServiceStub(channel)
        metadata = (("x-api-key", os.environ["GRPC_API_KEY"]),)
        for method in (
            "SearchFlights",
            "GetFlight",
            "UpdateFlight",
            "ReserveSeats",
            "ReleaseReservation",
        ):
            setattr(client, method, partial(getattr(client, method), metadata=metadata))
        yield client


@pytest.fixture(scope="session")
def sentinel():
    addresses = [
        address.rsplit(":", 1) for address in os.environ["REDIS_SENTINELS"].split(",")
    ]
    return Sentinel([(host, int(port)) for host, port in addresses], socket_timeout=0.5)


@pytest.fixture(scope="session")
def cache(sentinel):
    return sentinel.master_for("flight-cache", socket_timeout=0.5)


@pytest.fixture(scope="session")
def booking_db():
    with psycopg.connect(
        os.environ["TEST_BOOKING_DATABASE_URL"], autocommit=True
    ) as connection:
        yield connection


@pytest.fixture(scope="session")
def flight_db():
    with psycopg.connect(
        os.environ["TEST_FLIGHT_DATABASE_URL"], autocommit=True
    ) as connection:
        yield connection


@pytest.fixture
def new_flight(flight_db, booking_db, cache):
    ids = []

    def create(**changes):
        row = {
            "id": uuid4(),
            "flight_number": f"T{uuid4().hex[:12]}",
            "airline": "Test Airline",
            "origin": "SVO",
            "destination": "LED",
            "departure_time": datetime(2026, 12, 1, 9, tzinfo=UTC),
            "arrival_time": datetime(2026, 12, 1, 11, tzinfo=UTC),
            "total_seats": 4,
            "available_seats": 4,
            "price": Decimal("1234.56"),
            "status": "SCHEDULED",
        }
        row.update(changes)
        flight_db.execute(
            """INSERT INTO flights
            (id, flight_number, airline, origin, destination, departure_time,
             arrival_time, total_seats, available_seats, price, status)
            VALUES (%(id)s, %(flight_number)s, %(airline)s, %(origin)s,
                    %(destination)s, %(departure_time)s, %(arrival_time)s,
                    %(total_seats)s, %(available_seats)s, %(price)s, %(status)s)""",
            row,
        )
        ids.append(row["id"])
        for key in cache.scan_iter(match="search:*"):
            cache.delete(key)
        return row

    yield create
    for flight_id in ids:
        booking_db.execute("DELETE FROM bookings WHERE flight_id = %s", [flight_id])
        flight_db.execute(
            "DELETE FROM seat_reservations WHERE flight_id = %s", [flight_id]
        )
        flight_db.execute("DELETE FROM flights WHERE id = %s", [flight_id])
        cache.delete(f"flight:{flight_id}")
    for key in cache.scan_iter(match="search:*"):
        cache.delete(key)
