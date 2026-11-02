#!/usr/bin/env python3
"""
Argvtix Dual Service Launcher
Starts both FastAPI Backend (port 8000) and Vite Frontend (port 5173) simultaneously.
Press Ctrl+C to stop both services cleanly.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
UI_DIR = ROOT_DIR / "ui"

processes = []


def stream_logs(process, prefix, color_code):
    """Streams stdout/stderr lines with a colored prefix."""
    reset_code = "\033[0m"
    try:
        for line in iter(process.stdout.readline, ""):
            if not line:
                break
            print(f"{color_code}{prefix}{reset_code} {line.rstrip()}", flush=True)
    except Exception:
        pass


def cleanup(signum=None, frame=None):
    """Terminates all child processes cleanly."""
    print(
        "\n\033[1;33m[SHUTDOWN]\033[0m Stopping Argvtix Backend and Frontend services...",
        flush=True,
    )
    for p in processes:
        if p.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.call(
                        ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    p.terminate()
            except Exception:
                pass
    print("\033[1;32m[SHUTDOWN]\033[0m All services stopped successfully.", flush=True)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    banner = """
========================================================================
   ARGVTIX: Enterprise AI Reliability Platform (v1.2.0-prod)
   Zero-Bypass Gateway • Claim Grounding • State Watchdog
========================================================================
   Frontend Web App : http://127.0.0.1:5173/
   Platform Console : http://127.0.0.1:5173/overview
   Backend REST API : http://127.0.0.1:8000
   OpenAPI Swagger  : http://127.0.0.1:8000/docs
   WebSocket Stream : ws://127.0.0.1:8000/ws/events
========================================================================
   Press Ctrl+C to terminate both services.
========================================================================
"""
    print(banner, flush=True)

    # 1. Start Backend FastAPI via uvicorn
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "argvtix.gateway.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]

    print(
        "\033[1;34m[SYSTEM]\033[0m Spawning FastAPI backend on http://127.0.0.1:8000 ...",
        flush=True,
    )
    backend_env = dict(os.environ)
    src_dir = str(ROOT_DIR / "src")
    backend_env["PYTHONPATH"] = f"{src_dir};{backend_env.get('PYTHONPATH', '')}"
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    processes.append(backend_proc)

    # 2. Start Frontend Vite Dev Server
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"]

    print(
        "\033[1;35m[SYSTEM]\033[0m Spawning Vite frontend on http://127.0.0.1:5173 ...", flush=True
    )
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(UI_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(sys.platform == "win32"),
    )
    processes.append(frontend_proc)

    # Start stream reader threads
    t1 = threading.Thread(
        target=stream_logs, args=(backend_proc, "[BACKEND]", "\033[36m"), daemon=True
    )
    t2 = threading.Thread(
        target=stream_logs, args=(frontend_proc, "[FRONTEND]", "\033[32m"), daemon=True
    )
    t1.start()
    t2.start()

    # Keep alive until child exits or Ctrl+C
    try:
        while True:
            time.sleep(0.5)
            if backend_proc.poll() is not None:
                print("\033[1;31m[BACKEND EXITED]\033[0m Backend stopped.", flush=True)
                cleanup()
            if frontend_proc.poll() is not None:
                print("\033[1;31m[FRONTEND EXITED]\033[0m Frontend stopped.", flush=True)
                cleanup()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
