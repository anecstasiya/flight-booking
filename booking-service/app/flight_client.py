import os

import grpc
from contracts import flight_pb2 as pb
from contracts import flight_pb2_grpc as rpc
from fastapi import HTTPException

ADDRESS = os.getenv("FLIGHT_SERVICE_ADDRESS", "localhost:50051")
TIMEOUT = float(os.getenv("GRPC_TIMEOUT_SECONDS", "3"))


def call_flight(method, request):
    with grpc.insecure_channel(ADDRESS) as channel:
        stub = rpc.FlightServiceStub(channel)
        try:
            return getattr(stub, method)(request, timeout=TIMEOUT)
        except grpc.RpcError as error:
            status = {
                grpc.StatusCode.INVALID_ARGUMENT: 400,
                grpc.StatusCode.NOT_FOUND: 404,
                grpc.StatusCode.RESOURCE_EXHAUSTED: 409,
                grpc.StatusCode.FAILED_PRECONDITION: 409,
                grpc.StatusCode.ALREADY_EXISTS: 409,
                grpc.StatusCode.UNAVAILABLE: 503,
                grpc.StatusCode.DEADLINE_EXCEEDED: 504,
            }.get(error.code(), 502)
            detail = (
                error.details()
                if status in (400, 404, 409)
                else "Flight Service unavailable"
            )
            raise HTTPException(status_code=status, detail=detail) from None


def flight_data(flight):
    return {
        "id": flight.id,
        "flight_number": flight.flight_number,
        "airline": flight.airline,
        "origin": flight.origin,
        "destination": flight.destination,
        "departure_time": flight.departure_time.ToJsonString(),
        "arrival_time": flight.arrival_time.ToJsonString(),
        "total_seats": flight.total_seats,
        "available_seats": flight.available_seats,
        "price": flight.price,
        "status": pb.FlightStatus.Name(flight.status),
    }
