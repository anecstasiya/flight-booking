from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import grpc
import pytest
from contracts import flight_pb2 as pb


def booking_body(flight, **changes):
    body = {
        "user_id": str(uuid4()),
        "flight_id": str(flight["id"]),
        "passenger_name": "Test Passenger",
        "passenger_email": "passenger@example.com",
        "seat_count": 2,
    }
    body.update(changes)
    return body


def available(stub, flight):
    return stub.GetFlight(
        pb.GetFlightRequest(flight_id=str(flight["id"])), timeout=3
    ).available_seats


def test_search_and_get(api, new_flight):
    first = new_flight()
    second = new_flight(
        departure_time=datetime(2026, 12, 2, 9, tzinfo=UTC),
        arrival_time=datetime(2026, 12, 2, 11, tzinfo=UTC),
    )
    cancelled = new_flight(status="CANCELLED")
    other = new_flight(origin="VKO")
    query = {"origin": "SVO", "destination": "LED"}
    response = api.get("/flights", params=query)
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert {str(first["id"]), str(second["id"])} <= ids
    assert str(cancelled["id"]) not in ids
    assert str(other["id"]) not in ids
    response = api.get("/flights", params={**query, "date": "2026-12-01"})
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert str(first["id"]) in ids
    assert str(second["id"]) not in ids
    response = api.get(f"/flights/{first['id']}")
    assert response.status_code == 200
    assert Decimal(response.json()["price"]) == first["price"]
    assert response.json()["status"] == "SCHEDULED"
    assert api.get(f"/flights/{uuid4()}").status_code == 404
    assert api.get("/flights/invalid").status_code == 422


def test_booking_round_trip(api, stub, new_flight, flight_db):
    flight = new_flight()
    body = booking_body(flight)
    response = api.post("/bookings", json=body)
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "CONFIRMED"
    assert Decimal(booking["total_price"]) == Decimal("2469.12")
    assert available(stub, flight) == 2
    reservation = flight_db.execute(
        "SELECT seat_count, status FROM seat_reservations WHERE booking_id = %s",
        [UUID(booking["id"])],
    ).fetchone()
    assert reservation == (2, "ACTIVE")
    assert (
        api.patch(f"/flights/{flight['id']}", json={"price": "9999.99"}).status_code
        == 200
    )
    assert api.get(f"/bookings/{booking['id']}").json() == booking
    response = api.get("/bookings", params={"user_id": body["user_id"]})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [booking["id"]]
    assert api.get("/bookings", params={"user_id": str(uuid4())}).json() == []
    response = api.post(f"/bookings/{booking['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert available(stub, flight) == 4
    assert api.post(f"/bookings/{booking['id']}/cancel").status_code == 409
    assert available(stub, flight) == 4
    assert flight_db.execute(
        "SELECT status FROM seat_reservations WHERE booking_id = %s",
        [UUID(booking["id"])],
    ).fetchone() == ("RELEASED",)


def test_failed_reservation_creates_no_booking(api, stub, new_flight, booking_db):
    flight = new_flight()
    assert (
        api.post("/bookings", json=booking_body(flight, seat_count=5)).status_code
        == 409
    )
    assert available(stub, flight) == 4
    assert booking_db.execute(
        "SELECT count(*) FROM bookings WHERE flight_id = %s", [flight["id"]]
    ).fetchone() == (0,)
    assert (
        api.post(
            "/bookings", json=booking_body(flight, flight_id=str(uuid4()))
        ).status_code
        == 404
    )
    cancelled = new_flight(status="CANCELLED")
    assert api.post("/bookings", json=booking_body(cancelled)).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"seat_count": 0},
        {"seat_count": -1},
        {"seat_count": True},
        {"passenger_email": "invalid"},
        {"passenger_name": " "},
        {"user_id": ""},
        {"flight_id": "invalid"},
    ],
)
def test_invalid_booking(api, new_flight, changes):
    flight = new_flight()
    assert (
        api.post("/bookings", json=booking_body(flight, **changes)).status_code == 422
    )


def test_missing_and_invalid_requests(api):
    assert api.get("/flights").status_code == 422
    assert (
        api.get("/flights", params={"origin": "svo", "destination": "LED"}).status_code
        == 422
    )
    assert (
        api.get(
            "/flights", params={"origin": "SVO", "destination": "LED", "date": "wrong"}
        ).status_code
        == 422
    )
    assert api.get("/bookings").status_code == 422
    assert api.get(f"/bookings/{uuid4()}").status_code == 404
    assert api.post(f"/bookings/{uuid4()}/cancel").status_code == 404


def test_grpc_errors(stub, new_flight):
    flight = new_flight()
    requests = [
        (
            "GetFlight",
            pb.GetFlightRequest(flight_id="bad"),
            grpc.StatusCode.INVALID_ARGUMENT,
        ),
        (
            "GetFlight",
            pb.GetFlightRequest(flight_id=str(uuid4())),
            grpc.StatusCode.NOT_FOUND,
        ),
        ("SearchFlights", pb.SearchFlightsRequest(), grpc.StatusCode.INVALID_ARGUMENT),
        (
            "ReserveSeats",
            pb.ReserveSeatsRequest(
                flight_id=str(flight["id"]), booking_id=str(uuid4()), seat_count=0
            ),
            grpc.StatusCode.INVALID_ARGUMENT,
        ),
        (
            "ReleaseReservation",
            pb.ReleaseReservationRequest(booking_id=str(uuid4())),
            grpc.StatusCode.NOT_FOUND,
        ),
    ]
    for method, request, code in requests:
        with pytest.raises(grpc.RpcError) as error:
            getattr(stub, method)(request, timeout=3)
        assert error.value.code() == code


def test_repeat_reservation_and_release(stub, new_flight):
    flight = new_flight()
    request = pb.ReserveSeatsRequest(
        flight_id=str(flight["id"]), booking_id=str(uuid4()), seat_count=1
    )
    first = stub.ReserveSeats(request, timeout=3)
    assert stub.ReserveSeats(request, timeout=3).id == first.id
    assert available(stub, flight) == 3
    request.seat_count = 2
    with pytest.raises(grpc.RpcError) as error:
        stub.ReserveSeats(request, timeout=3)
    assert error.value.code() == grpc.StatusCode.ALREADY_EXISTS
    release = pb.ReleaseReservationRequest(booking_id=request.booking_id)
    assert stub.ReleaseReservation(release, timeout=3).status == pb.RELEASED
    assert stub.ReleaseReservation(release, timeout=3).status == pb.RELEASED
    assert available(stub, flight) == 4
    request.seat_count = 1
    with pytest.raises(grpc.RpcError) as error:
        stub.ReserveSeats(request, timeout=3)
    assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION


def test_last_seat_cannot_be_sold_twice(api, stub, new_flight, booking_db):
    flight = new_flight(total_seats=1, available_seats=1)

    def reserve(_):
        return api.post(
            "/bookings", json=booking_body(flight, seat_count=1)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert sorted(results) == [201, 409]
    assert available(stub, flight) == 0
    assert booking_db.execute(
        "SELECT count(*) FROM bookings WHERE flight_id = %s", [flight["id"]]
    ).fetchone() == (1,)


def test_booking_database_error_releases_seats(
    api, stub, new_flight, booking_db, flight_db
):
    flight = new_flight(
        total_seats=1000, available_seats=1000, price=Decimal("9999999999.99")
    )
    response = api.post("/bookings", json=booking_body(flight, seat_count=1000))
    assert response.status_code == 503, response.text
    assert available(stub, flight) == 1000
    assert booking_db.execute(
        "SELECT count(*) FROM bookings WHERE flight_id = %s", [flight["id"]]
    ).fetchone() == (0,)
    assert flight_db.execute(
        "SELECT status FROM seat_reservations WHERE flight_id = %s", [flight["id"]]
    ).fetchall() == [("RELEASED",)]
