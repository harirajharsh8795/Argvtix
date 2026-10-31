"""
Multi-Process Concurrency & Distributed Invariant Verification Test.
Demonstrates that two completely independent operating system processes
(separate Python interpreters, heaps, and in-memory caches) executing
concurrent refund requests with the same idempotency key are governed
by atomic database constraints, committing exactly ONE refund row.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import pytest

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from earp.db.models import Base, Customer, Order, Payment, Refund


def test_multiprocess_atomic_refund_idempotency(tmp_path):
    """
    Spawns two completely separate OS Python processes that simultaneously invoke
    shop_tools.issue_refund against the same database using the identical idempotency key.
    """
    db_file = tmp_path / "mp_concurrency.db"
    db_url = f"sqlite:///{db_file}"

    # 1. Initialize schema and enable WAL mode for concurrent multi-process access
    engine = create_engine(db_url, connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(bind=engine)

    # 2. Seed data
    Session = sessionmaker(bind=engine)
    with Session() as s:
        cust = Customer(id="c_mp", name="MP User", email="mp@enterprise.internal", phone="+919876543210")
        ord1 = Order(id="o_mp", customer_id="c_mp", status="completed", subtotal=5000.0, tax=0.0, total_amount=5000.0)
        pay1 = Payment(id="p_mp", order_id="o_mp", customer_id="c_mp", amount=5000.0, status="succeeded")
        s.add_all([cust, ord1, pay1])
        s.commit()
    engine.dispose()

    # 3. Create standalone worker script executed in separate OS processes
    worker_script = tmp_path / "worker.py"
    worker_code = """
import sys, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from earp.target_app.tools import shop_tools

db_url = r"__DB_URL__"
engine = create_engine(db_url, connect_args={"timeout": 30})
Session = sessionmaker(bind=engine)

with Session() as s:
    try:
        res = shop_tools.issue_refund(
            db=s,
            customer_id="c_mp",
            order_id="o_mp",
            amount=1500.0,
            reason="multiprocess_test",
            idempotency_key="shared_idemp_key_123",
        )
        if not res.success:
            print(f"FAILED: {res.error}", file=sys.stderr)
            sys.exit(1)
        print(f"SUCCESS: {res.data.get('refund_id')}", file=sys.stdout)
    except Exception as exc:
        print(f"EXCEPTION: {exc}", file=sys.stderr)
        sys.exit(1)
""".replace("__DB_URL__", str(db_url))
    worker_script.write_text(worker_code, encoding="utf-8")

    src_dir = str(Path(__file__).resolve().parent.parent / "src")
    env = os.environ.copy()
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src_dir

    # 4. Launch 2 independent Python OS processes concurrently
    p1 = subprocess.Popen([sys.executable, str(worker_script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    p2 = subprocess.Popen([sys.executable, str(worker_script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    out1, err1 = p1.communicate(timeout=15)
    out2, err2 = p2.communicate(timeout=15)

    assert p1.returncode == 0, f"Process 1 failed with err: {err1.decode('utf-8', errors='replace')} out: {out1.decode('utf-8', errors='replace')}"
    assert p2.returncode == 0, f"Process 2 failed with err: {err2.decode('utf-8', errors='replace')} out: {out2.decode('utf-8', errors='replace')}"

    # 5. Verify database state: Exactly ONE row committed
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT id, customer_id, order_id, amount, idempotency_key FROM refunds WHERE idempotency_key='shared_idemp_key_123'")
    rows = cur.fetchall()
    conn.close()

    assert len(rows) == 1, f"Expected exactly 1 committed refund across processes, found {len(rows)}!"
    assert rows[0][4] == "shared_idemp_key_123"
    assert rows[0][3] == 1500.0
