import logging
import os
import threading
import time
from collections import deque

import grpc

logger = logging.getLogger(__name__)
TRANSIENT = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}


class CircuitOpen(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.UNAVAILABLE

    def details(self):
        return "Flight Service circuit is open"


class ResilienceInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(self):
        self.threshold = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
        self.reset = float(os.getenv("CB_RESET_SECONDS", "10"))
        self.window = float(os.getenv("CB_WINDOW_SECONDS", "60"))
        self.delay = float(os.getenv("GRPC_RETRY_DELAY", "0.1"))
        if min(self.threshold, self.reset, self.window, self.delay) <= 0:
            raise ValueError("Resilience settings must be positive")
        self.state = "CLOSED"
        self.opened = 0
        self.failures = deque()
        self.lock = threading.Lock()

    def transition(self, state):
        logger.warning("Circuit breaker: %s -> %s", self.state, state)
        self.state = state

    def before_call(self):
        with self.lock:
            if self.state == "OPEN":
                if time.monotonic() - self.opened < self.reset:
                    raise CircuitOpen()
                self.transition("HALF_OPEN")
                return True
            if self.state == "HALF_OPEN":
                raise CircuitOpen()
            return False

    def after_call(self, failed, probe):
        with self.lock:
            now = time.monotonic()
            if probe:
                if failed:
                    self.opened = now
                    self.transition("OPEN")
                else:
                    self.failures.clear()
                    self.transition("CLOSED")
            elif self.state == "CLOSED" and failed:
                while self.failures and now - self.failures[0] > self.window:
                    self.failures.popleft()
                self.failures.append(now)
                if len(self.failures) >= self.threshold:
                    self.opened = now
                    self.transition("OPEN")

    def intercept_unary_unary(self, continuation, details, request):
        probe = self.before_call()
        for attempt in range(3):
            call = continuation(details, request)
            failed = call.code() in TRANSIENT
            if not failed or attempt == 2:
                self.after_call(failed, probe)
                return call
            logger.info("gRPC retry %s: %s", attempt + 1, details.method)
            time.sleep(self.delay * 2**attempt)
