"""
memory/store.py
───────────────
Layer 3 — Persistent memory storage using fakeredis.

In production: swap fakeredis.FakeRedis() for redis.Redis(host, port).
That's the only change needed — interface is identical.

Stores per-customer memory as JSON in Redis with no TTL (permanent).
Key pattern: customer_memory:{customer_id}
"""

import json
import fakeredis
from dataclasses import dataclass

# One shared fakeredis instance — simulates a persistent Redis server
# In production: redis.Redis(host="localhost", port=6379, db=0)
_redis = fakeredis.FakeRedis(decode_responses=True)

KEY_PREFIX = "customer_memory"


def _key(customer_id: str) -> str:
    return f"{KEY_PREFIX}:{customer_id}"


def save_memories(customer_id: str, memories: list[dict]) -> None:
    """Saves customer memories to Redis. Overwrites existing."""
    _redis.set(_key(customer_id), json.dumps(memories))


def load_memories(customer_id: str) -> list[dict]:
    """Loads customer memories from Redis. Returns empty list if none."""
    raw = _redis.get(_key(customer_id))
    return json.loads(raw) if raw else []


def delete_memories(customer_id: str) -> None:
    """Deletes all memories for a customer (GDPR compliance)."""
    _redis.delete(_key(customer_id))


def list_customers() -> list[str]:
    """Returns all customer IDs that have stored memories."""
    keys = _redis.keys(f"{KEY_PREFIX}:*")
    return [k.replace(f"{KEY_PREFIX}:", "") for k in keys]


def memory_exists(customer_id: str) -> bool:
    return _redis.exists(_key(customer_id)) > 0