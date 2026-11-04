import time

from redis.exceptions import RedisError

from redis import Redis


def test_sentinel_promotes_replica(api, new_flight, sentinel, cache):
    flight = new_flight()
    path = f"/flights/{flight['id']}"
    assert api.get(path).status_code == 200
    deadline = time.monotonic() + 20
    while not sentinel.discover_slaves("flight-cache"):
        assert time.monotonic() < deadline
        time.sleep(0.2)
    old_master = sentinel.discover_master("flight-cache")
    with Redis(host=old_master[0], port=old_master[1], socket_timeout=12) as master:
        master.set("check:replication", "ready", ex=30)
        assert master.wait(1, 10000) == 1
        master.shutdown(nosave=True)
    assert api.patch(path, json={"price": "4000.00"}).status_code == 200
    assert api.get(path).json()["price"] == "4000.00"
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            new_master = sentinel.discover_master("flight-cache")
            if new_master != old_master and cache.ping():
                break
        except RedisError:
            pass
        time.sleep(0.2)
    else:
        raise AssertionError("Sentinel did not promote the replica")
    assert api.get(path).json()["price"] == "4000.00"
    assert cache.get(f"flight:{flight['id']}") is not None
    assert 0 < cache.ttl(f"flight:{flight['id']}") <= 600
