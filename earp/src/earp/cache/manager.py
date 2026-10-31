"""
Intelligent Caching Architecture for EARP / Proofline
Provides thread-safe in-memory LRU TTL caching with automatic fallback
and distributed Redis cache integration for horizontally scaled deployments.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Protocol

logger = logging.getLogger("earp.cache")


class CacheBackend(Protocol):
    """Protocol for cache backends."""

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def delete_pattern(self, pattern: str) -> int: ...
    def clear(self) -> None: ...
    def get_metrics(self) -> dict[str, Any]: ...


class InMemoryLRUTTLCache:
    """
    Thread-safe process-local in-memory cache with LRU eviction and time-to-live expiration.
    Guarantees bounded memory consumption and sub-millisecond lookups.
    """

    def __init__(self, maxsize: int = 5000):
        self.maxsize = maxsize
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _purge_expired(self, now: float) -> None:
        """Evict expired items from the cache."""
        expired_keys = [k for k, (_, exp) in self._cache.items() if exp < now]
        for k in expired_keys:
            del self._cache[k]

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            val, expire_at = self._cache[key]
            if expire_at < now:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end for LRU order
            self._cache.move_to_end(key)
            self._hits += 1
            return val

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> bool:
        now = time.time()
        expire_at = now + ttl_seconds
        with self._lock:
            if key in self._cache:
                self._cache[key] = (value, expire_at)
                self._cache.move_to_end(key)
                return True

            # Enforce maxsize via LRU eviction
            if len(self._cache) >= self.maxsize:
                self._purge_expired(now)
                if len(self._cache) >= self.maxsize:
                    # Pop oldest least-recently-used item
                    self._cache.popitem(last=False)
                    self._evictions += 1

            self._cache[key] = (value, expire_at)
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Invalidate keys matching wildcard pattern (e.g. 'stats:*')."""
        deleted = 0
        with self._lock:
            matching_keys = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
            for k in matching_keys:
                del self._cache[k]
                deleted += 1
        return deleted

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_ratio = round((self._hits / total) * 100, 2) if total > 0 else 0.0
            return {
                "backend": "in_memory_lru_ttl",
                "items_count": len(self._cache),
                "max_capacity": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_ratio_percent": hit_ratio,
                "evictions": self._evictions,
            }


class RedisCache:
    """
    Distributed Redis cache backend for multi-replica horizontal scaling.
    Safely degrades to in-memory fallback on network or connectivity failures.
    """

    def __init__(self, redis_url: str, fallback_cache: InMemoryLRUTTLCache):
        self.redis_url = redis_url
        self.fallback = fallback_cache
        self._client = None
        self._connected = False
        self._hits = 0
        self._misses = 0
        self._connect()

    def _connect(self) -> None:
        try:
            import redis

            self._client = redis.Redis.from_url(
                self.redis_url,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                decode_responses=True,
            )
            self._client.ping()
            self._connected = True
            logger.info("Connected to distributed Redis cache at %s", self.redis_url)
        except Exception as exc:
            self._connected = False
            logger.warning("Redis unavailable (%s); using in-memory cache fallback", exc)

    def get(self, key: str) -> Any | None:
        if not self._connected or not self._client:
            return self.fallback.get(key)

        try:
            raw = self._client.get(key)
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis get error for %s: %s; falling back", key, exc)
            return self.fallback.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> bool:
        if not self._connected or not self._client:
            return self.fallback.set(key, value, ttl_seconds)

        try:
            payload = json.dumps(value)
            self._client.setex(key, ttl_seconds, payload)
            # Also set in local fallback
            self.fallback.set(key, value, ttl_seconds)
            return True
        except Exception as exc:
            logger.warning("Redis set error for %s: %s; falling back", key, exc)
            return self.fallback.set(key, value, ttl_seconds)

    def delete(self, key: str) -> bool:
        self.fallback.delete(key)
        if not self._connected or not self._client:
            return True
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    def delete_pattern(self, pattern: str) -> int:
        local_count = self.fallback.delete_pattern(pattern)
        if not self._connected or not self._client:
            return local_count

        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return local_count
        except Exception:
            return local_count

    def clear(self) -> None:
        self.fallback.clear()
        if self._connected and self._client:
            try:
                self._client.flushdb()
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_ratio = round((self._hits / total) * 100, 2) if total > 0 else 0.0
        return {
            "backend": "redis_distributed" if self._connected else "redis_fallback_to_memory",
            "redis_connected": self._connected,
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_ratio_percent": hit_ratio,
            "local_memory_stats": self.fallback.get_metrics(),
        }


class CacheManager:
    """
    Central Cache Manager for EARP.
    Automatically instantiates appropriate backend based on environment configuration.
    """

    def __init__(self):
        redis_url = os.getenv("REDIS_URL", os.getenv("PROOFLINE_REDIS_URL", ""))
        self._in_memory = InMemoryLRUTTLCache(maxsize=10000)

        if redis_url:
            self.backend: CacheBackend = RedisCache(redis_url, self._in_memory)
        else:
            self.backend = self._in_memory

    def get(self, key: str) -> Any | None:
        return self.backend.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> bool:
        return self.backend.set(key, value, ttl_seconds)

    def delete(self, key: str) -> bool:
        return self.backend.delete(key)

    def delete_pattern(self, pattern: str) -> int:
        return self.backend.delete_pattern(pattern)

    def clear(self) -> None:
        self.backend.clear()

    def get_metrics(self) -> dict[str, Any]:
        return self.backend.get_metrics()


# Global Singleton Instance
cache_manager = CacheManager()
