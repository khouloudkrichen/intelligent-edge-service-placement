"""Shared cache backend with optional Redis support and an in-memory fallback."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from config import CACHE_TTL_SECONDS, REDIS_URL


class _MemoryCache:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._entries.pop(key, None)
                return None
            return value

    def setex(self, key: str, ttl: int, value: str) -> None:
        with self._lock:
            self._entries[key] = (time.time() + ttl, value)


class CacheManager:
    def __init__(self) -> None:
        self._memory_backend = _MemoryCache()
        self._backend: Any = self._memory_backend
        self._initialized = False
        self._lock = threading.Lock()
        self.backend_name = "memory"

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            try:
                import redis

                client = redis.Redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.4,
                    socket_timeout=0.4,
                )
                client.ping()
                self._backend = client
                self.backend_name = "redis"
                print(f"Cache: Redis connected ({REDIS_URL})")
            except Exception as exc:
                self._use_memory_fallback(exc)
            self._initialized = True

    def _use_memory_fallback(self, exc: Exception) -> None:
        self._backend = self._memory_backend
        self.backend_name = "memory"
        print(f"Cache: Redis unavailable; fallback memory cache used ({exc})")

    @staticmethod
    def _key(namespace: str, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"ibn:{namespace}:{digest}"

    def get_json(self, namespace: str, key: str) -> Any | None:
        self.initialize()
        storage_key = self._key(namespace, key)
        try:
            raw = self._backend.get(storage_key)
        except Exception as exc:
            self._use_memory_fallback(exc)
            raw = self._backend.get(storage_key)
        if raw is None:
            print(f"Cache miss: {namespace}")
            return None
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            print(f"Cache miss: {namespace} (invalid cached data)")
            return None
        print(f"Cache hit: {namespace}")
        return value

    def set_json(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> None:
        self.initialize()
        storage_key = self._key(namespace, key)
        payload = json.dumps(value, ensure_ascii=False)
        try:
            self._backend.setex(storage_key, ttl or CACHE_TTL_SECONDS, payload)
        except Exception as exc:
            self._use_memory_fallback(exc)
            self._backend.setex(storage_key, ttl or CACHE_TTL_SECONDS, payload)


_cache = CacheManager()


def get_cache() -> CacheManager:
    _cache.initialize()
    return _cache
