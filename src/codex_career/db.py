from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from .ids import new_id
from .migrations import MIGRATIONS


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def migrate(self) -> None:
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            has_legacy = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='profile'"
            ).fetchone()
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            current = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
            if has_legacy and current == 0:
                connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(1, ?)", (now(),))
                current = 1
            for version, sql in MIGRATIONS:
                if version <= current:
                    continue
                connection.executescript(sql)
                connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (version, now()))
            self._backfill_public_ids(connection)
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _backfill_public_ids(connection: sqlite3.Connection) -> None:
        for table, prefix in (
            ("evidence", "evd"), ("jobs", "job"), ("material_sets", "mat"),
            ("applications", "app"), ("automation_runs", "run"), ("preparations", "prep"),
        ):
            for row_id, in connection.execute(f"SELECT id FROM {table} WHERE public_id IS NULL"):
                connection.execute(f"UPDATE {table} SET public_id=? WHERE id=?", (new_id(prefix), row_id))

    @property
    def schema_version(self) -> int:
        with self.connect() as connection:
            return connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def event(self, entity_type: str, entity_id: int, event_type: str, data: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO events(entity_type, entity_id, event_type, data_json, created_at) VALUES(?,?,?,?,?)",
                (entity_type, entity_id, event_type, json.dumps(data, sort_keys=True), now()),
            )
