"""Migrate the local demo SQLite data hub into PostgreSQL + pgvector."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kyungdong_agent.data_hub import PostgresRepository

BUSINESS_TABLES = (
    "projects", "designs", "materials", "incoming_inspections", "operations",
    "equipment_readings", "quote_predictions", "purchase_orders", "fat_tests", "claims", "rules",
)


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()]


def migrate(source: Path, database_url: str, replace: bool = True) -> dict[str, int]:
    if not source.exists():
        raise FileNotFoundError(f"SQLite 원본을 찾을 수 없습니다: {source}")
    target = PostgresRepository(database_url)
    if replace:
        target.reset_data_for_migration()
    counts: dict[str, int] = {}
    with sqlite3.connect(source) as sqlite:
        for table in BUSINESS_TABLES:
            data = rows(sqlite, table)
            counts[table] = target.insert_rows(table, data)
        docs = rows(sqlite, "knowledge_documents")
        counts["knowledge_documents"] = target.insert_knowledge_rows(docs)
        settings = rows(sqlite, "app_settings")
        for item in settings:
            target.save_setting(str(item["key"]), str(item["value"]))
        counts["app_settings"] = len(settings)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/kyungdong_demo.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL"))
    parser.add_argument("--append", action="store_true", help="기존 PostgreSQL 행을 보존하고 누락 행만 추가")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url 또는 DATABASE_URL이 필요합니다.")
    counts = migrate(args.source, args.database_url, replace=not args.append)
    print("PostgreSQL 마이그레이션 완료")
    for table, count in counts.items():
        print(f"- {table}: {count}건 처리")


if __name__ == "__main__":
    main()
