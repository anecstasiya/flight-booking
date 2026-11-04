import os
import signal
from concurrent import futures

import grpc
from contracts import flight_pb2_grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.service import FlightService


class DatabaseHealth(health_pb2_grpc.HealthServicer):
    def Check(self, request, context):
        if request.service:
            context.abort(grpc.StatusCode.NOT_FOUND, "Unknown service")
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return health_pb2.HealthCheckResponse(
                status=health_pb2.HealthCheckResponse.NOT_SERVING
            )
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightService(), server)
    health_pb2_grpc.add_HealthServicer_to_server(DatabaseHealth(), server)
    port = os.getenv("GRPC_PORT", "50051")
    if server.add_insecure_port(f"0.0.0.0:{port}") == 0:
        raise RuntimeError(f"Cannot bind gRPC port {port}")

    signal.signal(signal.SIGTERM, lambda *_: server.stop(grace=5))
    server.start()
    try:
        server.wait_for_termination()
    finally:
        server.stop(grace=5).wait()
        engine.dispose()


if __name__ == "__main__":
    serve()
