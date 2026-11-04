import importlib.util
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import grpc
import pytest
from contracts import flight_pb2 as pb
from contracts import flight_pb2_grpc as rpc


@pytest.fixture
def resilience(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "booking-service/app/resilience.py"
    spec = importlib.util.spec_from_file_location("resilience", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("CB_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("CB_RESET_SECONDS", "1")
    monkeypatch.setenv("CB_WINDOW_SECONDS", "2")
    monkeypatch.setenv("GRPC_RETRY_DELAY", "0.001")
    clock = SimpleNamespace(now=0, delays=[])
    clock.monotonic = lambda: clock.now
    clock.sleep = lambda delay: clock.delays.append(delay)
    module.time = clock
    return module, module.ResilienceInterceptor(), clock


def invoke(interceptor, code):
    continuation = Mock(return_value=SimpleNamespace(code=lambda: code))
    interceptor.intercept_unary_unary(
        continuation, SimpleNamespace(method="GetFlight"), None
    )
    return continuation.call_count


@pytest.mark.parametrize(
    "code", [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED]
)
def test_retry_limit_and_backoff(resilience, code):
    _, interceptor, clock = resilience
    assert invoke(interceptor, code) == 3
    assert clock.delays == [0.001, 0.002]


@pytest.mark.parametrize(
    "code",
    [
        grpc.StatusCode.INVALID_ARGUMENT,
        grpc.StatusCode.NOT_FOUND,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        grpc.StatusCode.UNAUTHENTICATED,
    ],
)
def test_business_errors_are_not_retried(resilience, code):
    _, interceptor, clock = resilience
    for _ in range(3):
        assert invoke(interceptor, code) == 1
    assert interceptor.state == "CLOSED"
    assert clock.delays == []


def test_breaker_open_and_single_probe(resilience, caplog):
    module, interceptor, clock = resilience
    for _ in range(2):
        invoke(interceptor, grpc.StatusCode.UNAVAILABLE)
    continuation = Mock()
    with pytest.raises(module.CircuitOpen):
        interceptor.intercept_unary_unary(continuation, None, None)
    continuation.assert_not_called()
    clock.now += 1
    entered, finish = threading.Event(), threading.Event()

    def probe(details, request):
        entered.set()
        assert finish.wait(3)
        return SimpleNamespace(code=lambda: grpc.StatusCode.OK)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(interceptor.intercept_unary_unary, probe, None, None)
        assert entered.wait(3)
        with pytest.raises(module.CircuitOpen):
            interceptor.intercept_unary_unary(continuation, None, None)
        finish.set()
        future.result()
    assert interceptor.state == "CLOSED"
    assert "CLOSED -> OPEN" in caplog.text
    assert "OPEN -> HALF_OPEN" in caplog.text
    assert "HALF_OPEN -> CLOSED" in caplog.text


def test_failed_probe_reopens_and_window_expires(resilience):
    _, interceptor, clock = resilience
    invoke(interceptor, grpc.StatusCode.UNAVAILABLE)
    clock.now += 3
    invoke(interceptor, grpc.StatusCode.UNAVAILABLE)
    assert interceptor.state == "CLOSED"
    invoke(interceptor, grpc.StatusCode.UNAVAILABLE)
    assert interceptor.state == "OPEN"
    clock.now += 1
    invoke(interceptor, grpc.StatusCode.UNAVAILABLE)
    assert interceptor.state == "OPEN"


def test_retry_after_lost_reservation_response(resilience, stub, new_flight, flight_db):
    _, interceptor, _ = resilience
    flight = new_flight()
    booking_id = str(uuid4())
    calls = []

    def reserve(request, context):
        response = stub.ReserveSeats(request, timeout=3)
        calls.append(request.booking_id)
        if len(calls) == 1:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Response lost")
        return response

    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    server.add_generic_rpc_handlers(
        [
            grpc.method_handlers_generic_handler(
                "flightbooking.v1.FlightService",
                {
                    "ReserveSeats": grpc.unary_unary_rpc_method_handler(
                        reserve,
                        request_deserializer=pb.ReserveSeatsRequest.FromString,
                        response_serializer=pb.SeatReservation.SerializeToString,
                    )
                },
            )
        ]
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        with grpc.insecure_channel(f"127.0.0.1:{port}") as raw:
            client = rpc.FlightServiceStub(grpc.intercept_channel(raw, interceptor))
            response = client.ReserveSeats(
                pb.ReserveSeatsRequest(
                    flight_id=str(flight["id"]), booking_id=booking_id, seat_count=1
                ),
                timeout=3,
            )
        assert response.status == pb.ACTIVE
        assert calls == [booking_id, booking_id]
        assert flight_db.execute(
            "SELECT available_seats FROM flights WHERE id = %s", [flight["id"]]
        ).fetchone() == (3,)
        assert flight_db.execute(
            "SELECT count(*) FROM seat_reservations WHERE booking_id = %s", [booking_id]
        ).fetchone() == (1,)
    finally:
        server.stop(grace=0).wait()
