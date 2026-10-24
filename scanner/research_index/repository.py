"""Point-in-time, read-only access to a versioned research index."""

import hashlib
import re
import sqlite3
from pathlib import Path

from scanner.research import AssetIdentity
from scanner.research_index.builder import IndexManifest
from scanner.research_index.models import CandidateBatch, CandidateHit, CandidateQuery


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _fts_query(text):
    tokens = re.findall(r"[\w]+", text.casefold(), re.UNICODE)
    return " OR ".join(f'"{token}"' for token in tokens if len(token) >= 2)


class ResearchIndex:
    def __init__(self, path):
        self.path = Path(path)
        manifest_path = self.path.with_suffix(self.path.suffix + ".manifest.json")
        self.manifest = IndexManifest.model_validate_json(manifest_path.read_bytes())
        if _sha(self.path.read_bytes()) != self.manifest.database_sha256:
            raise ValueError("research index integrity error")

    def _connect(self):
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    def coverage(self, as_of):
        with self._connect() as connection:
            total = connection.execute("SELECT count(*) FROM asset").fetchone()[0]
            visible = connection.execute(
                "SELECT count(*) FROM asset WHERE available_at IS NOT NULL AND available_at<=?",
                (as_of.isoformat(),),
            ).fetchone()[0]
        return {
            "indexed_assets": total,
            "visible_assets": visible,
            "as_of": as_of.isoformat(),
            "payload_sha256": self.manifest.payload_sha256,
            "counts": self.manifest.counts,
        }

    def candidates(self, query, *, as_of, limit=50):
        query = CandidateQuery.model_validate(query)
        if not 1 <= limit <= 50:
            raise ValueError("candidate limit must be between 1 and 50")
        coverage = self.coverage(as_of)
        if not query.constrained():
            return CandidateBatch(
                status="insufficiently_constrained",
                candidates=[],
                full_universe_size=coverage["indexed_assets"],
                visible_universe_size=coverage["visible_assets"],
                matched_before_limit=0,
                limit=limit,
                index_payload_sha256=self.manifest.payload_sha256,
            )
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM asset WHERE available_at IS NOT NULL AND available_at<=?",
                (as_of.isoformat(),),
            ).fetchall()
            evidence_rows = connection.execute(
                "SELECT * FROM evidence WHERE available_at<=?", (as_of.isoformat(),)
            ).fetchall()
            by_asset = {}
            for row in evidence_rows:
                by_asset.setdefault(row["asset_id"], []).append(row)
            text_assets = None
            if (query.text or "").strip():
                expression = _fts_query(query.text)
                if not expression:
                    text_assets = set()
                else:
                    matches = connection.execute(
                        """
                        SELECT DISTINCT f.asset_id FROM search_fts f
                        LEFT JOIN evidence e ON e.source_id=f.source_id
                        JOIN asset a ON a.asset_id=f.asset_id
                        WHERE search_fts MATCH ? AND a.available_at<=?
                          AND (e.source_id IS NULL OR e.available_at<=?)
                        """,
                        (expression, as_of.isoformat(), as_of.isoformat()),
                    ).fetchall()
                    text_assets = {row[0] for row in matches}
        hits = []
        for row in rows:
            if text_assets is not None and row["asset_id"] not in text_assets:
                continue
            confirmed, contradicted, unknown = [], [], []
            for field, values, label in (
                ("sector", query.sectors, "sector"),
                ("country", query.countries, "country"),
            ):
                candidate = row[field]
                for expected in values:
                    marker = f"{label}:{expected}"
                    if candidate is None:
                        unknown.append(marker)
                    elif candidate == expected:
                        confirmed.append(marker)
                    else:
                        contradicted.append(marker)
            evidence = by_asset.get(row["asset_id"], [])
            available_types = {item["event_type"] for item in evidence}
            for expected in [*query.event_types, *query.fact_claims]:
                marker = f"event:{expected}"
                (confirmed if expected in available_types else unknown).append(marker)
            if text_assets is not None:
                confirmed.append(f"text:{query.text}")
            score = len(confirmed) * 10 - len(contradicted) * 8
            hits.append(
                CandidateHit(
                    identity=AssetIdentity.model_validate_json(row["identity_json"]),
                    score=score,
                    confirmed=confirmed,
                    contradicted=contradicted,
                    unknown=unknown,
                    evidence_source_ids=sorted(item["source_id"] for item in evidence)[:8],
                )
            )
        hits.sort(
            key=lambda item: (
                -item.score,
                len(item.contradicted),
                item.identity.name,
                item.identity.cik or "",
            )
        )
        return CandidateBatch(
            status="ok" if hits else "unresolved",
            candidates=hits[:limit],
            full_universe_size=coverage["indexed_assets"],
            visible_universe_size=coverage["visible_assets"],
            matched_before_limit=len(hits),
            limit=limit,
            index_payload_sha256=self.manifest.payload_sha256,
        )

    def evidence(self, identity, *, as_of, kinds):
        identity = AssetIdentity.model_validate(identity)
        asset_id = next(
            (
                f"{kind}:{getattr(identity, kind)}"
                for kind in ("cik", "isin", "wkn", "lei")
                if getattr(identity, kind)
            ),
            None,
        )
        if asset_id is None:
            return {"status": "unavailable", "records": []}
        with self._connect() as connection:
            placeholders = ",".join("?" for _ in kinds)
            rows = connection.execute(
                f"""SELECT * FROM evidence
                WHERE asset_id=? AND available_at<=? AND kind IN ({placeholders})
                ORDER BY available_at,source_id""",
                (asset_id, as_of.isoformat(), *sorted(kinds)),
            ).fetchall()
        return {
            "status": "ok" if rows else "unavailable",
            "records": [dict(row) for row in rows],
            "as_of": as_of.isoformat(),
        }
