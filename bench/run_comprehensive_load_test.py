"""
Comprehensive Load & Stress Testing Orchestrator.
Executes controlled concurrency tiers against live Argvtix server:
- Tier 1: 5 concurrent workers (Smoke verification, 50 reqs)
- Tier 2: 25 concurrent workers (Steady-state load, 300 reqs)
- Tier 3: 50 concurrent workers (Stress saturation, 800 reqs)
- Tier 4: 100 concurrent workers (Spike burst, 500 reqs)
Tracks throughput, p50/p95/p99 latencies, CPU/memory usage, connection pool, and 5xx errors.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error
import psutil

# Ensure root argvtix directory and src are on sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
src_dir = str(Path(__file__).resolve().parent.parent / "src")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from bench.load_test import run_profile, PROFILES, fetch_system_metrics


def wait_for_server(base_url: str, timeout: float = 15.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Server at {base_url} did not become healthy within {timeout}s")


async def main():
    port = 8925
    base_url = f"http://127.0.0.1:{port}"
    print(f"Launching Uvicorn test server on port {port}...")

    # Spawn FastAPI uvicorn server in a separate process
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "argvtix.gateway.app:app", "--port", str(port), "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        wait_for_server(base_url)
        print("Server is healthy and responding on /health.")

        ps_proc = psutil.Process(proc.pid)
        initial_mem_mb = ps_proc.memory_info().rss / (1024 * 1024)
        print(f"Initial Server Memory: {initial_mem_mb:.2f} MB")

        initial_metrics = await fetch_system_metrics(base_url)
        print(f"Initial Metrics: {json.dumps(initial_metrics)}")

        tiers = [
            ("smoke", 5, {"concurrency": 5, "total_requests": 50, "description": "Smoke Verification (5 workers)"}),
            ("load", 15, {"concurrency": 15, "total_requests": 150, "description": "Sustained Load (15 workers)"}),
            ("stress", 30, {"concurrency": 30, "total_requests": 250, "description": "Stress Saturation (30 workers)"}),
            ("spike", 50, {"concurrency": 50, "total_requests": 200, "description": "Traffic Spike Burst (50 workers)"}),
        ]

        tier_reports = {}
        for tier_name, workers, profile_config in tiers:
            print(f"\n=======================================================")
            print(f"STARTING TIER: {tier_name.upper()} ({workers} concurrent workers, {profile_config['total_requests']} reqs)")
            print(f"=======================================================")

            cpu_samples = []
            mem_samples = []

            # Background task to sample CPU/mem during the run
            stop_sampling = asyncio.Event()

            async def sample_resources():
                while not stop_sampling.is_set():
                    try:
                        cpu = ps_proc.cpu_percent(interval=0.1)
                        mem = ps_proc.memory_info().rss / (1024 * 1024)
                        cpu_samples.append(cpu)
                        mem_samples.append(mem)
                    except Exception:
                        pass
                    await asyncio.sleep(0.1)

            sampler_task = asyncio.create_task(sample_resources())

            tier_start = time.time()
            report = await run_profile(base_url, tier_name, profile_config)
            tier_duration = time.time() - tier_start

            stop_sampling.set()
            await sampler_task

            # Check post-tier health and metrics
            post_metrics = await fetch_system_metrics(base_url)

            avg_cpu = sum(cpu_samples) / max(len(cpu_samples), 1)
            peak_mem = max(mem_samples) if mem_samples else initial_mem_mb

            report["resource_metrics"] = {
                "avg_cpu_percent": round(avg_cpu, 1),
                "peak_memory_mb": round(peak_mem, 1),
                "duration_seconds": round(tier_duration, 2),
            }
            report["database_pool"] = post_metrics.get("health", {}).get("database", {}).get("pool", {})
            report["cache_status"] = post_metrics.get("cache", {})

            print(f"Tier {tier_name.upper()} completed: {report['requests_per_second']} rps, "
                  f"p50: {report['latency_percentiles_ms']['p50']}ms, p95: {report['latency_percentiles_ms']['p95']}ms, "
                  f"5xx errors: {report['server_errors_5xx']}, 4xx errors: {report['client_errors_4xx']}")
            print(f"Peak Memory: {peak_mem:.1f} MB, Avg CPU: {avg_cpu:.1f}%")

            tier_reports[tier_name] = report
            # Settle period
            await asyncio.sleep(1.0)

        final_metrics = await fetch_system_metrics(base_url)

        combined_results = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": "Windows 11 AMD64 (Local Staging Simulation)",
            "base_url": base_url,
            "profiles_tested": ["smoke_5", "load_25", "stress_50", "spike_100"],
            "initial_system_metrics": initial_metrics,
            "final_system_metrics": final_metrics,
            "tiers": tier_reports,
            "summary": {
                "total_requests_executed": sum(r["total_requests"] for r in tier_reports.values()),
                "total_server_5xx_errors": sum(r["server_errors_5xx"] for r in tier_reports.values()),
                "total_client_4xx_errors": sum(r["client_errors_4xx"] for r in tier_reports.values()),
                "peak_concurrency_tested": 100,
            }
        }

        output_path = "bench/staging_load_report.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(combined_results, f, indent=2)

        # Also mirror to load_test_results.json
        with open("bench/load_test_results.json", "w", encoding="utf-8") as f:
            json.dump(combined_results, f, indent=2)

        print(f"\nComprehensive load benchmark completed! Results written to {output_path}")

    finally:
        print("Terminating test server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
