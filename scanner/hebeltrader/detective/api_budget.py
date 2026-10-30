"""Atomic, pessimistic monthly API reservations in a dedicated private ledger."""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class ApiBudget:
    def __init__(self, path, *, cap_cents=2000):
        if not 1 <= cap_cents <= 2000:
            raise ValueError("Monthly API reservation cap must be EUR 0.01–20.00")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cap_cents = cap_cents
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations "
                "(id INTEGER PRIMARY KEY, month TEXT, provider TEXT, cents INTEGER, at TEXT)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS ledger_meta (key TEXT PRIMARY KEY, value TEXT)")
            migrated = db.execute("SELECT value FROM ledger_meta WHERE key='pricing_v2'").fetchone()
            if migrated is None:
                # V1 charged a fictional EUR 0.05/0.10 per call. One cent is a
                # conservative ceiling for the configured Tavily Basic request and
                # bounded GPT-4.1-mini request at the published provider tariffs.
                db.execute("UPDATE reservations SET cents=1 WHERE cents>1")
                db.execute("INSERT INTO ledger_meta VALUES('pricing_v2','2026-10-29')")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, provider, cents):
        if provider not in ("search", "ai") or cents <= 0:
            raise ValueError("Invalid API reservation")
        now = datetime.now(UTC)
        month = now.strftime("%Y-%m")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
            count = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE month=? AND provider=?", (month, provider)
            ).fetchone()[0]
            if used + cents > self.cap_cents or count >= (1500 if provider == "search" else 600):
                raise ValueError("Monthly API budget exhausted")
            db.execute(
                "INSERT INTO reservations(month,provider,cents,at) VALUES(?,?,?,?)",
                (month, provider, cents, now.isoformat()),
            )

    def summary(self):
        with self._db() as db:
            month = datetime.now(UTC).strftime("%Y-%m")
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
            rows = db.execute(
                "SELECT provider, COUNT(*), COALESCE(SUM(cents),0) "
                "FROM reservations WHERE month=? GROUP BY provider",
                (month,),
            ).fetchall()
        per_provider = {provider: (calls, cents) for provider, calls, cents in rows}
        return {
            "month": month,
            "reserved_cents": used,
            "cap_cents": self.cap_cents,
            "remaining_cents": max(self.cap_cents - used, 0),
            "providers": {
                "search": {
                    "calls": per_provider.get("search", (0, 0))[0],
                    "reserved_cents": per_provider.get("search", (0, 0))[1],
                },
                "ai": {
                    "calls": per_provider.get("ai", (0, 0))[0],
                    "reserved_cents": per_provider.get("ai", (0, 0))[1],
                },
            },
            "accounting": "conservative_call_ceiling_not_provider_invoice",
        }
