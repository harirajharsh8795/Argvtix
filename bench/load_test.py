"""
ARGVTIX Production-Grade Load and Stress Testing Suite
Implements Realistic User Journeys across Public & Protected API Endpoints.
Profiles:
  - Smoke: Quick verification of availability & 200 OK responses.
  - Load: Steady-state normal production traffic.
  - Stress: High concurrency to discover system limits and pool saturation.
  - Spike: Sudden concurrent burst to evaluate rate-limiting & cache protection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from typing import Any

import httpx

# User journeys & request distribution weights
USER_JOURNEYS = [
    {
        "name": "Health Check",
        "method": "GET",
        "path": "/health",
        "weight": 15,
        "payload": None,
    },
    {
        "name": "Cache Metrics",
        "method": "GET",
        "path": "/api/v1/cache/metrics",
        "weight": 10,
        "payload": None,
    },
    {
        "name": "Trace Stats (Cached)",
        "method": "GET",
        "path": "/api/v1/traces/stats",
        "weight": 25,
        "payload": None,
    },
    {
        "name": "Trace History Filter",
        "method": "GET",
        "path": "/api/v1/traces?limit=20&status=success",
        "weight": 15,
        "payload": None,
    },
    {
        "name": "Guard Approvals Queue",
        "method": "GET",
        "path": "/api/v1/guard/approvals?status=pending",
        "weight": 10,
        "payload": None,
    },
    {
        "name": "Watchdog Anomaly Report",
        "method": "GET",
        "path": "/api/v1/watchdog/anomaly/report",
        "weight": 10,
        "payload": None,
    },
    {
        "name": "Action Guard Evaluation",
        "method": "POST",
        "path": "/api/v1/guard/check",
        "weight": 10,
        "factory": lambda: {
            "workflow_type": "refund",
            "tool_name": "issue_refund",
            "customer_id": "cust_synth_001",
            "order_id": f"ord_{uuid.uuid4().hex[:8]}",
            "amount": 29.99,
            "reason": "customer return",
            "metadata": {"source": "load_test"},
        },
    },
    {
        "name": "Contact Form Submission",
        "method": "POST",
        "path": "/api/v1/contact",
        "weight": 5,
        "factory": lambda: {
            "name": f"Tester {uuid.uuid4().hex[:4]}",
            "email": f"tester_{uuid.uuid4().hex[:6]}@argvtix.ai",
            "company": "LoadTest Corp",
            "use_case": "Evaluation of AI Agent Reliability Guardrails in production.",
            "turnstile_token": None,
            "honeypot": None,
        },
    },
]

PROFILES = {
    "smoke": {
        "concurrency": 5,
        "total_requests": 50,
        "description": "Smoke Verification: 5 concurrent workers, 50 requests total.",
    },
    "load": {
        "concurrency": 15,
        "total_requests": 150,
        "description": "Steady-State Load: 15 concurrent workers, 150 requests total.",
    },
    "stress": {
        "concurrency": 30,
        "total_requests": 300,
        "description": "Stress Saturation: 30 concurrent workers, 300 requests total.",
    },
    "spike": {
        "concurrency": 50,
        "total_requests": 250,
        "description": "Traffic Spike Burst: 50 concurrent workers, 250 requests burst.",
    },
}


class RequestResult:
    def __init__(
        self,
        endpoint_name: str,
        method: str,
        status_code: int,
        latency_ms: float,
        error: str | None = None,
    ):
        self.endpoint_name = endpoint_name
        self.method = method
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.error = error


async def execute_request(
    client: httpx.AsyncClient,
    base_url: str,
    journey: dict[str, Any],
) -> RequestResult:
    method = journey["method"]
    path = journey["path"]
    name = journey["name"]
    url = f"{base_url.rstrip('/')}{path}"
    payload = journey.get("factory")() if "factory" in journey else journey.get("payload")

    start_time = time.perf_counter()
    status_code = 0
    error_msg = None

    try:
        if method == "GET":
            resp = await client.get(url, timeout=20.0)
        elif method == "POST":
            resp = await client.post(url, json=payload, timeout=20.0)
        else:
            raise ValueError(f"Unsupported method: {method}")

        status_code = resp.status_code
        if status_code >= 500:
            error_msg = f"HTTP {status_code}: {resp.text[:100]}"
    except Exception as exc:
        error_msg = str(exc)
        status_code = 0

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return RequestResult(
        endpoint_name=name,
        method=method,
        status_code=status_code,
        latency_ms=elapsed_ms,
        error=error_msg,
    )


async def run_profile(
    base_url: str,
    profile_name: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    concurrency = config["concurrency"]
    total_requests = config["total_requests"]

    print(f"\n" + "=" * 70)
    print(f"RUNNING PROFILE: {profile_name.upper()}")
    print(f"Target: {base_url} | Concurrency: {concurrency} | Total Requests: {total_requests}")
    print(f"Scenario: {config['description']}")
    print("=" * 70)

    # Build weighted request pool
    weighted_journeys: list[dict[str, Any]] = []
    for journey in USER_JOURNEYS:
        weighted_journeys.extend([journey] * journey["weight"])

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    import random

    for _ in range(total_requests):
        queue.put_nowait(random.choice(weighted_journeys))

    results: list[RequestResult] = []
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)

    wall_start = time.perf_counter()

    is_asgi = base_url.lower() in ("asgi", "app", "in_process")
    if is_asgi:
        from argvtix.gateway.app import app
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver", limits=limits)
        target_url = "http://testserver"
    else:
        client = httpx.AsyncClient(base_url=base_url, limits=limits)
        target_url = base_url

    async with client:
        async def worker():
            while not queue.empty():
                try:
                    journey = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                res = await execute_request(client, target_url, journey)
                results.append(res)
                queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)

    wall_time = time.perf_counter() - wall_start
    rps = len(results) / wall_time if wall_time > 0 else 0.0

    # Aggregate metrics
    latencies = [r.latency_ms for r in results]
    latencies.sort()
    successful = [r for r in results if 200 <= r.status_code < 400]
    client_errs = [r for r in results if 400 <= r.status_code < 500]
    server_errs = [r for r in results if r.status_code >= 500 or r.status_code == 0]

    def percentile(p: float) -> float:
        if not latencies:
            return 0.0
        k = (len(latencies) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1
        if c < len(latencies):
            d0 = latencies[f] * (c - k)
            d1 = latencies[c] * (k - f)
            return d0 + d1
        return latencies[f]

    p50 = percentile(50.0)
    p95 = percentile(95.0)
    p99 = percentile(99.0)
    avg_lat = statistics.mean(latencies) if latencies else 0.0
    min_lat = min(latencies) if latencies else 0.0
    max_lat = max(latencies) if latencies else 0.0

    # Per-endpoint stats
    endpoint_stats: dict[str, dict[str, Any]] = {}
    for r in results:
        ep = r.endpoint_name
        if ep not in endpoint_stats:
            endpoint_stats[ep] = {"count": 0, "success": 0, "failed": 0, "latencies": []}
        endpoint_stats[ep]["count"] += 1
        if 200 <= r.status_code < 400:
            endpoint_stats[ep]["success"] += 1
        else:
            endpoint_stats[ep]["failed"] += 1
        endpoint_stats[ep]["latencies"].append(r.latency_ms)

    endpoint_summary = {}
    for ep, data in endpoint_stats.items():
        ep_lats = sorted(data["latencies"])
        endpoint_summary[ep] = {
            "requests": data["count"],
            "success": data["success"],
            "failed": data["failed"],
            "success_rate": round(data["success"] / data["count"] * 100.0, 2),
            "p50_ms": round(ep_lats[int(len(ep_lats) * 0.50)], 2),
            "p95_ms": round(ep_lats[int(len(ep_lats) * 0.95)], 2) if len(ep_lats) > 1 else round(ep_lats[0], 2),
            "avg_ms": round(statistics.mean(ep_lats), 2),
        }

    report = {
        "profile": profile_name,
        "concurrency": concurrency,
        "total_requests": len(results),
        "successful_requests": len(successful),
        "client_errors_4xx": len(client_errs),
        "server_errors_5xx": len(server_errs),
        "wall_time_sec": round(wall_time, 2),
        "requests_per_second": round(rps, 2),
        "latency_percentiles_ms": {
            "min": round(min_lat, 2),
            "avg": round(avg_lat, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "max": round(max_lat, 2),
        },
        "endpoints": endpoint_summary,
    }

    # Console display
    print(f"Results Summary:")
    print(f"  Throughput:           {rps:8.2f} req/sec")
    print(f"  Total Duration:       {wall_time:8.2f} seconds")
    print(f"  Successful (2xx/3xx): {len(successful)} / {len(results)} ({len(successful)/len(results)*100.0:.1f}%)")
    print(f"  Client Errors (4xx):  {len(client_errs)}")
    print(f"  Server Errors (5xx):  {len(server_errs)}")
    print(f"  Latency Percentiles:")
    print(f"    p50 (Median):       {p50:8.2f} ms")
    print(f"    p95:                {p95:8.2f} ms")
    print(f"    p99:                {p99:8.2f} ms")
    print(f"    Avg:                {avg_lat:8.2f} ms")
    print(f"    Max:                {max_lat:8.2f} ms")
    print("-" * 70)
    print(f"{'Endpoint':<28} | {'Reqs':<5} | {'p50 (ms)':<8} | {'p95 (ms)':<8} | {'Success %':<9}")
    print("-" * 70)
    for ep, ep_data in endpoint_summary.items():
        print(f"{ep:<28} | {ep_data['requests']:<5} | {ep_data['p50_ms']:<8.2f} | {ep_data['p95_ms']:<8.2f} | {ep_data['success_rate']:<9.1f}%")
    print("=" * 70)

    return report


async def fetch_system_metrics(base_url: str) -> dict[str, Any]:
    is_asgi = base_url.lower() in ("asgi", "app", "in_process")
    if is_asgi:
        from argvtix.gateway.app import app
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    else:
        client = httpx.AsyncClient(base_url=base_url)

    async with client:
        try:
            health_resp = await client.get("/health", timeout=15.0)
            health_json = health_resp.json() if health_resp.status_code == 200 else {}
        except Exception:
            health_json = {}

        try:
            cache_resp = await client.get("/api/v1/cache/metrics", timeout=15.0)
            cache_json = cache_resp.json() if cache_resp.status_code == 200 else {}
        except Exception:
            cache_json = {}

        return {
            "health": health_json,
            "cache": cache_json,
        }


async def main():
    parser = argparse.ArgumentParser(description="ARGVTIX Load Testing Suite")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Target API URL")
    parser.add_argument(
        "--profile",
        default="all",
        choices=["smoke", "load", "stress", "spike", "all"],
        help="Test profile to execute",
    )
    parser.add_argument("--output", default="bench/load_test_results.json", help="Output JSON path")
    args = parser.parse_args()

    print(f"Targeting ARGVTIX API at {args.url}")
    initial_metrics = await fetch_system_metrics(args.url)
    print(f"Initial Cache Status: {json.dumps(initial_metrics['cache'])}")

    profiles_to_run = (
        ["smoke", "load", "stress", "spike"]
        if args.profile == "all"
        else [args.profile]
    )

    all_reports = {}
    for prof in profiles_to_run:
        report = await run_profile(args.url, prof, PROFILES[prof])
        all_reports[prof] = report
        # Brief pause between test profiles to allow connection reuse and queue settling
        await asyncio.sleep(1.0)

    final_metrics = await fetch_system_metrics(args.url)
    print(f"\nFinal Cache Status: {json.dumps(final_metrics['cache'])}")

    combined_output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": args.url,
        "initial_metrics": initial_metrics,
        "final_metrics": final_metrics,
        "profiles": all_reports,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(combined_output, f, indent=2)

    # Mirror to bench/staging_load_report.json
    staging_report_path = "bench/staging_load_report.json"
    with open(staging_report_path, "w", encoding="utf-8") as f:
        json.dump(combined_output, f, indent=2)

    print(f"\nBenchmark suite complete. Full results written to {args.output} and {staging_report_path}")


if __name__ == "__main__":
    asyncio.run(main())
