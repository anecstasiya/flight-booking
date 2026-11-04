import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import grpc
import pytest
from contracts import flight_pb2 as pb
from contracts import flight_pb2_grpc as rpc
from grpc_health.v1 import health_pb2, health_pb2_grpc


@pytest.mark.parametrize("key", [None, "wrong"])
def test_auth_for_every_method(key):
    metadata = () if key is None else (("x-api-key", key),)
    with grpc.insecure_channel(os.environ["FLIGHT_SERVICE_ADDRESS"]) as channel:
        client = rpc.FlightServiceStub(channel)
        for method, request in [
            (client.SearchFlights, pb.SearchFlightsRequest()),
            (client.GetFlight, pb.GetFlightRequest()),
            (client.UpdateFlight, pb.UpdateFlightRequest()),
            (client.ReserveSeats, pb.ReserveSeatsRequest()),
            (client.ReleaseReservation, pb.ReleaseReservationRequest()),
            (
                health_pb2_grpc.HealthStub(channel).Check,
                health_pb2.HealthCheckRequest(),
            ),
        ]:
            with pytest.raises(grpc.RpcError) as error:
                method(request, metadata=metadata, timeout=3)
            assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_cache_aside_ttl_and_invalidation(api, stub, new_flight, cache):
    flight = new_flight()
    path = f"/flights/{flight['id']}"
    key = f"flight:{flight['id']}"
    query = {"origin": "SVO", "destination": "LED", "date": "2026-12-01"}
    search = "search:SVO:LED:2026-12-01"
    assert api.get(path).status_code == 200
    assert pb.Flight.FromString(cache.get(key)).available_seats == 4
    assert 0 < cache.ttl(key) <= 600
    hits = cache.info("stats")["keyspace_hits"]
    assert api.get(path).status_code == 200
    assert cache.info("stats")["keyspace_hits"] > hits
    assert api.get("/flights", params=query).status_code == 200
    assert 0 < cache.ttl(search) <= 600
    assert api.patch(path, json={"price": "2000.00"}).status_code == 200
    assert cache.get(key) is None
    assert cache.get(search) is None
    assert api.get(path).json()["price"] == "2000.00"
    assert api.get("/flights", params=query).status_code == 200
    booking_id = str(uuid4())
    stub.ReserveSeats(
        pb.ReserveSeatsRequest(
            flight_id=str(flight["id"]), booking_id=booking_id, seat_count=1
        ),
        timeout=3,
    )
    assert cache.get(key) is None
    assert cache.get(search) is None
    assert api.get(path).json()["available_seats"] == 3
    stub.ReleaseReservation(
        pb.ReleaseReservationRequest(booking_id=booking_id), timeout=3
    )
    assert cache.get(key) is None
    assert api.get(path).json()["available_seats"] == 4
    assert api.patch(path, json={"status": "CANCELLED"}).status_code == 200
    assert str(flight["id"]) not in {
        row["id"] for row in api.get("/flights", params=query).json()
    }


def test_parallel_reads_do_not_restore_stale_cache(api, new_flight):
    flight = new_flight()
    path = f"/flights/{flight['id']}"
    with ThreadPoolExecutor(max_workers=4) as pool:
        reads = [pool.submit(api.get, path) for _ in range(10)]
        assert api.patch(path, json={"price": "3000.00"}).status_code == 200
        for read in reads:
            assert read.result().status_code == 200
    assert api.get(path).json()["price"] == "3000.00"


@pytest.mark.parametrize(
    "body", [{}, {"price": "0"}, {"price": "NaN"}, {"status": "BAD"}]
)
def test_invalid_flight_update(api, new_flight, body):
    flight = new_flight()
    assert api.patch(f"/flights/{flight['id']}", json=body).status_code == 422
