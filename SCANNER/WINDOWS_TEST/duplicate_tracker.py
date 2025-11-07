# duplicate_tracker.py - Windows compatible duplicate tracking

import sqlite3
import os
from datetime import datetime

class DuplicateTracker:
    """Track scanned QR codes per batch to detect duplicates."""
    
    def __init__(self, db_path="scan_state.db"):
        """Initialize tracker with SQLite database."""
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scanned_qr (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_number TEXT NOT NULL,
                qr_code TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(batch_number, qr_code)
            )
        """)
        conn.commit()
        conn.close()
    
    def already_scanned(self, batch_number: str, qr_code: str) -> bool:
        """Check if QR code was already scanned for this batch."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM scanned_qr WHERE batch_number = ? AND qr_code = ?",
            (batch_number, qr_code)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def record_scan(self, batch_number: str, qr_code: str):
        """Record a scanned QR code."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute(
                "INSERT INTO scanned_qr (batch_number, qr_code, timestamp) VALUES (?, ?, ?)",
                (batch_number, qr_code, timestamp)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Already exists
        conn.close()
    
    def clear_batch(self, batch_number: str):
        """Clear all scans for a batch."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scanned_qr WHERE batch_number = ?", (batch_number,))
        conn.commit()
        conn.close()
    
    def get_batch_count(self, batch_number: str) -> int:
        """Get count of scanned QR codes for a batch."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM scanned_qr WHERE batch_number = ?",
            (batch_number,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
