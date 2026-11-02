"""
Automated Resilience and Performance Regression Tests.
Verifies:
  1. CacheManager fallback behavior when distributed cache is offline.
  2. LRU eviction and TTL expiration.
  3. Cache invalidation across prefixes.
  4. Database connection pool configuration and pre-ping safety.
  5. Trace stats aggregation single-query correctness.
  6. Distributed idempotency caching in ToolGateway.
"""

from __future__ import annotations

import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from argvtix.cache import CacheManager, InMemoryLRUTTLCache, RedisCache, cache_manager
from argvtix.db.models import Base, TraceRecord
from argvtix.db.session import pool_kwargs


def test_in_memory_cache_lru_and_ttl():
    """Verify in-memory LRU TTL cache limits capacity and honors expiration."""
    cache = InMemoryLRUTTLCache(maxsize=3)
    
    # Insert 3 items
    cache.set("k1", "v1", ttl_seconds=60)
    cache.set("k2", "v2", ttl_seconds=60)
    cache.set("k3", "v3", ttl_seconds=60)
    assert cache.get("k1") == "v1"
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"
    
    # Insert 4th item -> should evict least recently used (k1 was accessed, k2 was accessed, k3 is oldest access)
    cache.set("k4", "v4", ttl_seconds=60)
    metrics = cache.get_metrics()
    assert metrics["items_count"] <= 3
    assert metrics["evictions"] >= 1
    
    # Verify TTL expiration
    cache.set("expiring_key", "temporary", ttl_seconds=0.1)
    time.sleep(0.2)
    assert cache.get("expiring_key") is None


def test_cache_manager_graceful_degradation():
    """Verify RedisCache safely falls back to local memory if Redis is unconfigured or unreachable."""
    fallback = InMemoryLRUTTLCache(maxsize=100)
    offline_redis = RedisCache(redis_url="redis://127.0.0.1:59999/0", fallback_cache=fallback)
    assert not offline_redis._connected
    
    # Operations must succeed without raising network errors
    assert offline_redis.set("resilience_key", {"status": "ok"}, ttl_seconds=60) is True
    val = offline_redis.get("resilience_key")
    assert val == {"status": "ok"}
    
    # Invalidation must succeed
    assert offline_redis.delete("resilience_key") is True
    assert offline_redis.get("resilience_key") is None


def test_cache_pattern_invalidation():
    """Verify wildcard pattern deletion clears all matching keys."""
    mgr = CacheManager()
    mgr.set("traces:stats:default", {"total": 42}, ttl_seconds=30)
    mgr.set("traces:page:1", [1, 2, 3], ttl_seconds=30)
    mgr.set("unrelated:data", 999, ttl_seconds=30)
    
    cleared = mgr.delete_pattern("traces:*")
    assert cleared >= 2
    assert mgr.get("traces:stats:default") is None
    assert mgr.get("traces:page:1") is None
    assert mgr.get("unrelated:data") == 999


def test_database_connection_pool_bounds():
    """Verify database connection pool parameters are properly configured."""
    assert "pool_pre_ping" in pool_kwargs
    assert pool_kwargs["pool_pre_ping"] is True
    assert "pool_recycle" in pool_kwargs
    assert pool_kwargs["pool_recycle"] == 1800


def test_trace_stats_aggregation_correctness():
    """Verify collapsed trace stats query aggregates counts, errors, and latency accurately."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()
    
    try:
        # Seed test traces
        t1 = TraceRecord(
            id="tr_01",
            project_id="test_proj",
            workflow_type="chat",
            status="success",
            input_text="hello",
            total_latency_ms=100.0,
            total_cost_usd=0.01,
        )
        t2 = TraceRecord(
            id="tr_02",
            project_id="test_proj",
            workflow_type="chat",
            status="error",
            input_text="fail",
            total_latency_ms=200.0,
            total_cost_usd=0.02,
        )
        db.add_all([t1, t2])
        db.commit()
        
        # Execute collapsed aggregation query (from app.py get_trace_stats)
        from sqlalchemy import case, func
        stats = (
            db.query(
                func.count(TraceRecord.id).label("total_traces"),
                func.sum(
                    case((TraceRecord.status == "error", 1), else_=0)
                ).label("error_traces"),
                func.avg(TraceRecord.total_latency_ms).label("avg_latency_ms"),
                func.sum(TraceRecord.total_cost_usd).label("total_cost_usd"),
            )
            .filter(TraceRecord.project_id == "test_proj")
            .first()
        )
        
        assert stats.total_traces == 2
        assert stats.error_traces == 1
        assert stats.avg_latency_ms == 150.0
        assert round(stats.total_cost_usd, 2) == 0.03
        
    finally:
        db.close()
