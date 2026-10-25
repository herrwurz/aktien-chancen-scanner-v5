"""Local append-only SQLite archive for normalized research prices."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import MarketDataBatch


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value) -> str:
    return hashlib.sha256((_json(value) + "\n").encode()).hexdigest()


class MarketDataArchive:
    """An isolated artifact store; it never connects to application PostgreSQL."""

    def __init__(self, path, *, now=None, read_only=False):
        self.path = Path(path).resolve()
        self.read_only = read_only
        self.now = now or (lambda: datetime.now(UTC))
        if read_only:
            if not self.path.is_file():
                raise FileNotFoundError(self.path)
            self._validate_schema()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()

    def _connect(self):
        if self.read_only:
            connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        else:
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        if self.read_only:
            connection.execute("PRAGMA query_only=ON")
        return connection

    def _validate_schema(self):
        with self._connect() as db:
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"listing", "bar_revision", "corporate_action"} <= tables:
                raise ValueError("unsupported market archive schema")
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(bar_revision)").fetchall()
            }
            if "first_stored_at" not in columns:
                raise ValueError("market archive lacks first local storage time")

    def _initialize(self):
        with self._connect() as db:
            legacy_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(bar_revision)").fetchall()
            }
            if legacy_columns and "first_stored_at" not in legacy_columns:
                raise ValueError(
                    "legacy market archive cannot prove first local storage time; "
                    "rebuild from immutable raw snapshots"
                )
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS listing (
                    asset_id TEXT PRIMARY KEY,
                    identity_json TEXT NOT NULL,
                    identity_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bar_revision (
                    asset_id TEXT NOT NULL REFERENCES listing(asset_id),
                    provider TEXT NOT NULL,
                    session_date TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    value_sha256 TEXT NOT NULL,
                    bar_json TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    raw_sha256 TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    first_stored_at TEXT NOT NULL,
                    PRIMARY KEY (asset_id, provider, session_date, revision),
                    UNIQUE (asset_id, provider, session_date, value_sha256)
                );
                CREATE INDEX IF NOT EXISTS bar_as_of
                    ON bar_revision(asset_id, provider, session_date, retrieved_at, revision);
                CREATE TABLE IF NOT EXISTS corporate_action (
                    asset_id TEXT NOT NULL REFERENCES listing(asset_id),
                    provider TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    action_sha256 TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    PRIMARY KEY (asset_id, provider, action_sha256)
                );
                """
            )

    def import_batch(self, value: MarketDataBatch | dict) -> dict[str, int]:
        if self.read_only:
            raise ValueError("read-only market archive")
        batch = MarketDataBatch.model_validate(value)
        stored_at = self.now()
        if stored_at.utcoffset() is None:
            raise ValueError("aware storage clock required")
        stored_at = stored_at.astimezone(UTC)
        if batch.retrieved_at.astimezone(UTC) > stored_at:
            raise ValueError("provider retrieval follows local storage")
        identity = batch.instrument.model_dump(mode="json")
        identity_json, identity_sha = _json(identity), _digest(identity)
        result = {"inserted": 0, "unchanged": 0, "revised": 0}
        with self._connect() as db:
            existing = db.execute(
                "SELECT identity_sha256 FROM listing WHERE asset_id=?", (batch.instrument.asset_id,)
            ).fetchone()
            if existing and existing["identity_sha256"] != identity_sha:
                raise ValueError("listing identity conflict")
            db.execute(
                """INSERT OR IGNORE INTO listing
                   (asset_id, identity_json, identity_sha256) VALUES(?,?,?)""",
                (batch.instrument.asset_id, identity_json, identity_sha),
            )
            for bar in batch.bars:
                bar_value = bar.model_dump(mode="json")
                stable_value = {
                    key: value
                    for key, value in bar_value.items()
                    if key not in {"retrieved_at", "source_pointer"}
                }
                value_sha = _digest(stable_value)
                latest = db.execute(
                    """SELECT revision, value_sha256 FROM bar_revision
                       WHERE asset_id=? AND provider=? AND session_date=?
                       ORDER BY revision DESC LIMIT 1""",
                    (batch.instrument.asset_id, batch.provider, bar.session_date.isoformat()),
                ).fetchone()
                known = db.execute(
                    """SELECT 1 FROM bar_revision
                       WHERE asset_id=? AND provider=? AND session_date=? AND value_sha256=?""",
                    (
                        batch.instrument.asset_id,
                        batch.provider,
                        bar.session_date.isoformat(),
                        value_sha,
                    ),
                ).fetchone()
                if known:
                    result["unchanged"] += 1
                    continue
                revision = 1 if latest is None else latest["revision"] + 1
                db.execute(
                    """INSERT INTO bar_revision
                       (asset_id, provider, session_date, revision, value_sha256, bar_json,
                        manifest_sha256, raw_sha256, retrieved_at, first_stored_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        batch.instrument.asset_id,
                        batch.provider,
                        bar.session_date.isoformat(),
                        revision,
                        value_sha,
                        _json(bar_value),
                        batch.manifest_sha256,
                        batch.raw_sha256,
                        bar.retrieved_at.astimezone(UTC).isoformat(),
                        stored_at.isoformat(),
                    ),
                )
                result["inserted" if latest is None else "revised"] += 1
            for action in batch.actions:
                action_value = action.model_dump(mode="json")
                action_sha = _digest(action_value)
                db.execute(
                    """INSERT OR IGNORE INTO corporate_action
                       (asset_id, provider, effective_date, action_sha256, action_json,
                        manifest_sha256)
                       VALUES(?,?,?,?,?,?)""",
                    (
                        batch.instrument.asset_id,
                        batch.provider,
                        action.effective_date.isoformat(),
                        action_sha,
                        _json(action_value),
                        batch.manifest_sha256,
                    ),
                )
        return result

    def list_instruments(self):
        with self._connect() as db:
            rows = db.execute(
                "SELECT identity_json FROM listing ORDER BY asset_id"
            ).fetchall()
        return [json.loads(row["identity_json"]) for row in rows]

    def revision_history(self, asset_id: str, provider: str, session_date: str):
        with self._connect() as db:
            rows = db.execute(
                """SELECT revision, value_sha256, bar_json, manifest_sha256, raw_sha256
                   FROM bar_revision WHERE asset_id=? AND provider=? AND session_date=?
                   ORDER BY revision""",
                (asset_id, provider, session_date),
            ).fetchall()
        return [
            {
                "revision": row["revision"],
                "value_sha256": row["value_sha256"],
                "bar": json.loads(row["bar_json"]),
                "manifest_sha256": row["manifest_sha256"],
                "raw_sha256": row["raw_sha256"],
            }
            for row in rows
        ]

    def logical_sha256(self) -> str:
        with self._connect() as db:
            listings = [dict(row) for row in db.execute("SELECT * FROM listing ORDER BY asset_id")]
            bars = [
                dict(row)
                for row in db.execute(
                    """SELECT asset_id, provider, session_date, revision, value_sha256,
                              bar_json, manifest_sha256, raw_sha256, retrieved_at, first_stored_at
                       FROM bar_revision ORDER BY asset_id, provider, session_date, revision"""
                )
            ]
            actions = [
                dict(row)
                for row in db.execute(
                    """SELECT * FROM corporate_action
                       ORDER BY asset_id, provider, effective_date, action_sha256"""
                )
            ]
        return _digest({"listings": listings, "bars": bars, "actions": actions})

    def latest_session(self, asset_id: str, provider: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT MAX(session_date) AS latest FROM bar_revision
                   WHERE asset_id=? AND provider=?""",
                (asset_id, provider),
            ).fetchone()
        return row["latest"]

    def prices(self, asset_id, *, start, end, as_of, availability_mode="strict"):
        if availability_mode not in {"strict", "modeled"}:
            raise ValueError("invalid availability mode")
        if as_of.utcoffset() is None:
            raise ValueError("aware as_of required")
        params = [asset_id, start, end]
        condition = ""
        if availability_mode == "strict":
            condition = "AND first_stored_at <= ?"
            params.append(as_of.astimezone(UTC).isoformat())
        query = f"""
            SELECT * FROM bar_revision candidate
            WHERE asset_id=? AND session_date BETWEEN ? AND ? {condition}
              AND revision=(
                SELECT MAX(revision) FROM bar_revision visible
                WHERE visible.asset_id=candidate.asset_id
                  AND visible.provider=candidate.provider
                  AND visible.session_date=candidate.session_date
                  {condition.replace("first_stored_at", "visible.first_stored_at")}
              )
            ORDER BY session_date, provider
        """
        if availability_mode == "strict":
            params.append(as_of.astimezone(UTC).isoformat())
        with self._connect() as db:
            rows = db.execute(query, params).fetchall()
        prices = []
        for row in rows:
            bar = json.loads(row["bar_json"])
            available_at = datetime.fromisoformat(
                bar["retrieved_at"]
                if availability_mode == "strict"
                else bar["modeled_available_at"]
            )
            if available_at <= as_of:
                prices.append(
                    {
                        **bar,
                        "provider": row["provider"],
                        "revision": row["revision"],
                        "manifest_sha256": row["manifest_sha256"],
                        "raw_sha256": row["raw_sha256"],
                        "first_stored_at": row["first_stored_at"],
                    }
                )
        availability = (
            "observed_retrieval_time"
            if availability_mode == "strict"
            else "hypothetical_modeled_session_close"
        )
        return {
            "status": "available" if prices else "unavailable_at_as_of",
            "prices": prices,
            "availability": availability,
            "historical_availability_verified": False,
            "training_eligible": False,
            "as_of": as_of.isoformat(),
            "logical_sha256": self.logical_sha256(),
        }
