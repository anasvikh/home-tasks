from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .data_loaders import User


@dataclass
class Assignment:
    id: int
    task_date: date
    user_id: int
    room: str
    level: str
    description: str
    completed: bool
    completed_at: Optional[datetime]


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._ensure_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        try:
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_date TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    room TEXT NOT NULL,
                    level TEXT NOT NULL,
                    description TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT,
                    UNIQUE(task_date, user_id, room, level, description),
                    FOREIGN KEY(user_id) REFERENCES users(telegram_id)
                )
                """
            )

    def sync_users(self, users: Iterable[User]) -> None:
        with self.connect() as conn:
            for user in users:
                conn.execute(
                    "INSERT INTO users(telegram_id, name) VALUES(?, ?)"
                    " ON CONFLICT(telegram_id) DO UPDATE SET name=excluded.name",
                    (user.telegram_id, user.name),
                )

    def add_assignment(
        self,
        task_date: date,
        user_id: int,
        room: str,
        level: str,
        description: str,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO assignments(task_date, user_id, room, level, description)
                VALUES(?, ?, ?, ?, ?)
                """,
                (task_date.isoformat(), user_id, room, level, description),
            )
            if cursor.lastrowid:
                return cursor.lastrowid
            # fetch id for existing row
            existing = conn.execute(
                """
                SELECT id FROM assignments WHERE task_date=? AND user_id=? AND room=? AND level=? AND description=?
                """,
                (task_date.isoformat(), user_id, room, level, description),
            ).fetchone()
            return int(existing[0])

    def list_assignments_for_user(self, task_date: date, user_id: int) -> List[Assignment]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, task_date, user_id, room, level, description, completed, completed_at
                FROM assignments
                WHERE task_date=? AND user_id=?
                ORDER BY room, level, id
                """,
                (task_date.isoformat(), user_id),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def list_assignments(self, task_date: date) -> List[Assignment]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, task_date, user_id, room, level, description, completed, completed_at
                FROM assignments
                WHERE task_date=?
                ORDER BY user_id, room, level
                """,
                (task_date.isoformat(),),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def mark_completed(self, assignment_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE assignments SET completed=1, completed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), assignment_id),
            )

    def list_incomplete_for_user(self, task_date: date, user_id: int) -> List[Assignment]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, task_date, user_id, room, level, description, completed, completed_at
                FROM assignments
                WHERE task_date=? AND user_id=? AND completed=0
                ORDER BY room, level, id
                """,
                (task_date.isoformat(), user_id),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def daily_stats(self, start: date, end: date) -> List[Tuple[int, str, date, int, int]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT a.user_id, u.name, a.task_date,
                       SUM(CASE WHEN a.completed=1 THEN 1 ELSE 0 END) AS completed_count,
                       COUNT(*) AS total
                FROM assignments a
                JOIN users u ON u.telegram_id = a.user_id
                WHERE a.task_date BETWEEN ? AND ?
                GROUP BY a.user_id, u.name, a.task_date
                ORDER BY u.name, a.task_date
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()

        results: List[Tuple[int, str, date, int, int]] = []
        for row in rows:
            task_date = date.fromisoformat(str(row[2]))
            results.append(
                (
                    int(row[0]),
                    str(row[1]),
                    task_date,
                    int(row[3] or 0),
                    int(row[4] or 0),
                )
            )
        return results

    @staticmethod
    def _row_to_assignment(row: sqlite3.Row) -> Assignment:
        completed_at = row[7]
        return Assignment(
            id=int(row[0]),
            task_date=datetime.fromisoformat(row[1]).date(),
            user_id=int(row[2]),
            room=str(row[3]),
            level=str(row[4]),
            description=str(row[5]),
            completed=bool(row[6]),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        )
