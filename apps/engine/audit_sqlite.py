# apps/engine/audit_sqlite.py
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_conditions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  strategy TEXT NOT NULL,
  state TEXT NOT NULL,
  score REAL,
  payload_json TEXT NOT NULL
);
"""

class AuditSQLite:
    def __init__(self, path: str = "audit.db"):
        self.path = path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute(SCHEMA)
            conn.commit()

    def insert(self, symbol: str, timeframe: str, strategy: str, state: str, score: Optional[float], payload: Dict[str, Any]):
        record = {
            "metrics": payload.get("metrics"),
            "reasons": payload.get("reasons"),
        }
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO audit_conditions (ts, symbol, timeframe, strategy, state, score, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.utcnow().isoformat(),
                    symbol,
                    timeframe,
                    strategy,
                    state,
                    score,
                    json.dumps(record, ensure_ascii=False),
                ),
            )
            conn.commit()
