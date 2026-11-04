import logging
import os
import threading
from datetime import UTC
from uuid import UUID

import grpc
from contracts import flight_pb2 as pb
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry
from redis.sentinel import Sentinel

logger = logging.getLogger(__name__)


class CacheInterceptor(grpc.ServerInterceptor):
    def __init__(self):
        addresses = [
            (host, int(port))
            for host, port in (
                address.rsplit(":", 1)
                for address in os.environ["REDIS_SENTINELS"].split(",")
            )
        ]
        self.name = "flight-cache"
        self.sentinel = Sentinel(
            addresses, socket_timeout=0.2, socket_connect_timeout=0.2
        )
        self.client = self.sentinel.master_for(self.name, retry=Retry(NoBackoff(), 0))
        self.ttl = int(os.getenv("CACHE_TTL_SECONDS", "600"))
        if not 300 <= self.ttl <= 600:
            raise ValueError("CACHE_TTL_SECONDS must be between 300 and 600")
        self.master = None
        self.dirty = True
        self.lock = threading.Lock()

    def clear(self, *patterns):
        for pattern in patterns:
            for key in self.client.scan_iter(match=pattern):
                self.client.delete(key)

    def run(self, operation):
        try:
            master = self.sentinel.discover_master(self.name)
            if self.dirty or master != self.master:
                self.clear("flight:*", "search:*")
                self.master = master
                self.dirty = False
            return operation()
        except RedisError:
            self.dirty = True
            logger.warning("Cache unavailable, using PostgreSQL")

    def intercept_service(self, continuation, details):
        handler = continuation(details)
        method = details.method.rsplit("/", 1)[-1]
        if handler is None or method not in {
            "GetFlight",
            "SearchFlights",
            "UpdateFlight",
            "ReserveSeats",
            "ReleaseReservation",
        }:
            return handler

        def invoke(request, context):
            with self.lock:
                key = None
                try:
                    if method == "GetFlight":
                        key = f"flight:{UUID(request.flight_id)}"
                    elif method == "SearchFlights":
                        date = (
                            request.date.ToDatetime(tzinfo=UTC).date().isoformat()
                            if request.HasField("date")
                            else "all"
                        )
                        key = f"search:{request.origin}:{request.destination}:{date}"
                except (ValueError, OverflowError):
                    pass
                if key:
                    cached = self.run(lambda: self.client.get(key))
                    logger.info(
                        "cache %s: %s", "hit" if cached is not None else "miss", key
                    )
                    if cached is not None:
                        message = (
                            pb.Flight
                            if method == "GetFlight"
                            else pb.SearchFlightsResponse
                        )
                        return message.FromString(cached)
                response = handler.unary_unary(request, context)
                if key:
                    self.run(
                        lambda: self.client.set(
                            key, response.SerializeToString(), ex=self.ttl
                        )
                    )
                else:
                    flight_id = (
                        response.id if method == "UpdateFlight" else response.flight_id
                    )
                    self.run(lambda: self.clear(f"flight:{flight_id}", "search:*"))
                return response

        return grpc.unary_unary_rpc_method_handler(
            invoke,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
