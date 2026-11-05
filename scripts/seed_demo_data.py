"""
Single-command Demo Data Seeder for Argvtix / ShopOps.

Usage:
    python scripts/seed_demo_data.py [--orders 100]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from argvtix.db.session import SessionLocal, init_db
from argvtix.target_app.seed import seed_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Argvtix Demo Data Seeder")
    parser.add_argument("--orders", type=int, default=50, help="Number of demo orders to generate")
    args = parser.parse_args()

    print(f"[*] Initializing database and generating {args.orders} demo entities...")
    init_db()
    with SessionLocal() as session:
        stats = seed_database(session, order_count=args.orders)

    print("[+] Seeding complete! Database populated with:")
    for key, count in stats.items():
        print(f"    - {key}: {count}")


if __name__ == "__main__":
    main()
