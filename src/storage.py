from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.models import dump_json, utc_now_iso

DEFAULT_DB_PATH = Path("data/baton.sqlite3")


class BatonStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._create_schema()
        return self._conn

    def _create_schema(self) -> None:
        self._get_conn().executescript("""
            CREATE TABLE IF NOT EXISTS batons (
                namespace TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                data TEXT NOT NULL
            );
        """)

    def read(self, namespace: str) -> tuple[dict | None, str | None]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data, updated_at FROM batons WHERE namespace = ?",
            (namespace,),
        ).fetchone()
        if row is None:
            return None, None
        return json.loads(row["data"]), row["updated_at"]

    def write(self, namespace: str, data: dict) -> str:
        conn = self._get_conn()
        updated_at = utc_now_iso()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO batons (namespace, updated_at, data)
                VALUES (?, ?, ?)
                ON CONFLICT(namespace) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (namespace, updated_at, dump_json(data)),
            )
            conn.commit()
            return updated_at
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
