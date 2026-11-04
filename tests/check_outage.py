import os
import sys
import time
from uuid import uuid4

import httpx

with httpx.Client(base_url=os.environ["BOOKING_URL"], timeout=15) as client:
    path = f"/flights/{uuid4()}"
    if sys.argv[1] == "down":
        for _ in range(int(os.getenv("CB_FAILURE_THRESHOLD", "5"))):
            assert client.get(path).status_code == 503
        start = time.monotonic()
        assert client.get(path).status_code == 503
        assert time.monotonic() - start < 1
        print("OPEN returns 503 immediately")
    else:
        deadline = time.monotonic() + float(os.getenv("CB_RESET_SECONDS", "10")) + 15
        while time.monotonic() < deadline:
            if client.get(path).status_code == 404:
                print("HALF_OPEN probe succeeded, service recovered")
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Circuit breaker did not recover")
