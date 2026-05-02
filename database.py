import datetime
import logging
import sqlite3
import threading
from pathlib import Path

import pytz

from config import APP_TIMEZONE, DATABASE_FILE

logger = logging.getLogger(__name__)


class RecordsDatabase:
    def __init__(self, filename: str = DATABASE_FILE):
        self.filename = filename
        self._lock = threading.RLock()

    def _connect(self):
        conn = sqlite3.connect(self.filename)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True) if Path(self.filename).parent != Path(".") else None
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('Доход', 'Расход')),
                    amount REAL NOT NULL CHECK(amount > 0),
                    category TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    source TEXT,
                    source_row INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, source_row)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_created_at ON records(created_at)"
            )

    def _add_record(
        self,
        record_type: str,
        amount: float,
        category: str,
        comment: str = "",
        date_str: str | None = None,
        time_str: str | None = None,
        source: str | None = None,
        source_row: int | None = None,
    ):
        now = datetime.datetime.now(pytz.timezone(APP_TIMEZONE))
        date_str = date_str or now.strftime("%d.%m.%Y")
        time_str = time_str or now.strftime("%H:%M")
        comment = comment or ""

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO records (date, time, type, amount, category, comment, source, source_row)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (date_str, time_str, record_type, float(amount), category, comment, source, source_row),
            )
            record_id = cur.lastrowid

        return True, {
            "id": record_id,
            "date": date_str,
            "time": time_str,
            "type": record_type,
            "amount": float(amount),
            "category": category,
            "comment": comment,
        }

    async def add_record(self, *args, **kwargs):
        try:
            return self._add_record(*args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to add record to SQLite: {e}")
            return False, {}

    def _delete_record(self, record_id: int):
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
            return cur.rowcount > 0

    async def delete_record(self, record_id: int):
        try:
            return self._delete_record(record_id)
        except Exception as e:
            logger.error(f"Failed to delete record from SQLite: {e}")
            return False

    def _get_balance(self):
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN type = 'Доход' THEN amount
                        WHEN type = 'Расход' THEN -amount
                        ELSE 0
                    END
                ), 0) AS balance
                FROM records
                """
            ).fetchone()
            return float(row["balance"])

    async def get_balance(self):
        try:
            return self._get_balance()
        except Exception as e:
            logger.error(f"Failed to calculate SQLite balance: {e}")
            return None

    def _list_records(self):
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, time, type, amount, category, comment, created_at
                FROM records
                ORDER BY id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    async def list_records(self):
        return self._list_records()

    def import_records(self, records: list[dict]):
        inserted = 0
        skipped = 0
        with self._lock, self._connect() as conn:
            for record in records:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO records
                        (date, time, type, amount, category, comment, source, source_row)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["date"],
                        record["time"],
                        record["type"],
                        float(record["amount"]),
                        record["category"],
                        record.get("comment", ""),
                        record.get("source"),
                        record.get("source_row"),
                    ),
                )
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        return inserted, skipped


records_db = RecordsDatabase()
