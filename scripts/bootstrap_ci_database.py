"""Create local warehouse schemas and empty source tables for dbt CI."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg


def main() -> None:
    url = os.getenv(
        "PEOPLEPULSE_WAREHOUSE_DSN",
        "postgresql://peoplepulse:peoplepulse@localhost:5432/people_warehouse",
    )
    sql_path = Path("infrastructure/postgres/warehouse/001_warehouse.sql")
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql_path.read_text(encoding="utf-8"))
    print("Warehouse schemas initialized.")


if __name__ == "__main__":
    main()
