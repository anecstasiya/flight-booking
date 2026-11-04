import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc


def check():
    with grpc.insecure_channel("127.0.0.1:50051") as channel:
        response = health_pb2_grpc.HealthStub(channel).Check(
            health_pb2.HealthCheckRequest(), timeout=3
        )
    if response.status != health_pb2.HealthCheckResponse.SERVING:
        raise SystemExit("Flight Service is not serving")


if __name__ == "__main__":
    check()
