"""SQLite-backed duplicate tracking for scanned QR codes."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

_DB_FILENAME = "scan_state.db"


class DuplicateTracker:
    """Persist scanned QR codes per batch using SQLite."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        path = Path(db_path or _DB_FILENAME)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scanned_qr (
                batch TEXT NOT NULL,
                qr TEXT NOT NULL,
                PRIMARY KEY (batch, qr)
            )
            """
        )
        self._conn.commit()
        self._lock = threading.Lock()

    def already_scanned(self, batch: str, qr_code: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM scanned_qr WHERE batch = ? AND qr = ? LIMIT 1",
                (batch, qr_code),
            )
            return cur.fetchone() is not None

    def record_scan(self, batch: str, qr_code: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO scanned_qr (batch, qr) VALUES (?, ?)",
                (batch, qr_code),
            )
            self._conn.commit()

    def reset_batch(self, batch: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM scanned_qr WHERE batch = ?", (batch,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
