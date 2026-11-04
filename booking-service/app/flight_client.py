import os

import grpc
from contracts import flight_pb2_grpc as rpc
from fastapi import HTTPException
from google.protobuf.json_format import MessageToDict

from app.resilience import ResilienceInterceptor

ADDRESS = os.getenv("FLIGHT_SERVICE_ADDRESS", "localhost:50051")
TIMEOUT = float(os.getenv("GRPC_TIMEOUT_SECONDS", "3"))
API_KEY = os.environ["GRPC_API_KEY"]
resilience = ResilienceInterceptor()


def call_flight(method, request):
    with grpc.insecure_channel(ADDRESS, options=[("grpc.enable_retries", 0)]) as raw:
        channel = grpc.intercept_channel(raw, resilience)
        stub = rpc.FlightServiceStub(channel)
        try:
            return getattr(stub, method)(
                request, timeout=TIMEOUT, metadata=(("x-api-key", API_KEY),)
            )
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
    return MessageToDict(
        flight,
        preserving_proto_field_name=True,
        always_print_fields_with_no_presence=True,
    )
