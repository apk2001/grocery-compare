import time

_store = {}
TTL = 15 * 60  # 15 minutes


def get(key):
    hit = _store.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    return None


def put(key, value):
    _store[key] = (time.time(), value)
