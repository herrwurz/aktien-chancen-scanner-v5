"""Point-in-time, read-only access to a versioned research index."""

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from scanner.research import AssetIdentity
from scanner.research_index.builder import SCHEMA_VERSION, IndexManifest
from scanner.research_index.identity import canonicalize_identity, stable_asset_id
from scanner.research_index.models import CandidateBatch, CandidateHit, CandidateQuery


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _fts_query(text):
    tokens = re.findall(r"[\w]+", text.casefold(), re.UNICODE)
    return " AND ".join(f'"{token}"' for token in tokens if len(token) >= 2)


class ResearchIndex:
    def __init__(self, path):
        self.path = Path(path)
        manifest_path = self.path.with_suffix(self.path.suffix + ".manifest.json")
        self.manifest = IndexManifest.model_validate_json(manifest_path.read_bytes())
        if self.manifest.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported research index schema version")
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

    def resolve_identity(self, identity, *, as_of):
        """Resolve only exact identifiers and reject conflicting supplied metadata."""
        identity = canonicalize_identity(identity)
        identifiers = [
            (kind, getattr(identity, kind))
            for kind in ("cik", "isin", "wkn", "lei")
            if getattr(identity, kind)
        ]
        if not identifiers:
            return {"status": "unavailable", "reason": "stable_identifier_required"}
        with self._connect() as connection:
            matches = []
            for kind, value in identifiers:
                row = connection.execute(
                    f"SELECT * FROM asset WHERE {kind}=? AND available_at<=?",  # noqa: S608
                    (value, as_of.isoformat()),
                ).fetchone()
                if row is not None:
                    matches.append(row)
        if not matches:
            return {"status": "unavailable", "reason": "identity_not_visible_at_as_of"}
        asset_ids = {row["asset_id"] for row in matches}
        if len(asset_ids) != 1:
            return {"status": "identity_conflict", "reason": "identifiers_resolve_differently"}
        row = matches[0]
        indexed = AssetIdentity.model_validate_json(row["identity_json"])
        comparable = ("ticker", "exchange", "mic", "isin", "wkn", "lei", "cik")
        conflicts = [
            field
            for field in comparable
            if getattr(identity, field) is not None
            and getattr(indexed, field) is not None
            and getattr(identity, field) != getattr(indexed, field)
        ]
        if conflicts:
            return {
                "status": "identity_conflict",
                "reason": "supplied_identity_conflicts_with_index",
                "conflicting_fields": conflicts,
            }
        return {
            "status": "ok",
            "asset_id": row["asset_id"],
            "identity": indexed.model_dump(mode="json"),
        }

    def market_universe(self, *, as_of):
        """Return point-in-time-visible identities for deterministic provider pilots."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT identity_json FROM asset
                   WHERE available_at IS NOT NULL AND available_at<=?
                   ORDER BY asset_id""",
                (as_of.isoformat(),),
            ).fetchall()
        return [AssetIdentity.model_validate_json(row["identity_json"]) for row in rows]

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
                """SELECT e.* FROM evidence e
                WHERE e.available_at<=?
                  AND NOT EXISTS (
                    SELECT 1 FROM evidence revision
                    WHERE revision.asset_id=e.asset_id
                      AND revision.supersedes_source_id=e.source_id
                      AND revision.available_at<=?
                  )""",
                (as_of.isoformat(), as_of.isoformat()),
            ).fetchall()
            by_asset = {}
            for row in evidence_rows:
                by_asset.setdefault(row["asset_id"], []).append(row)
            identity_text_assets = None
            evidence_text_assets = None
            if (query.text or "").strip():
                expression = _fts_query(query.text)
                if not expression:
                    identity_text_assets, evidence_text_assets = set(), set()
                else:
                    matches = connection.execute(
                        """
                        SELECT DISTINCT f.asset_id,f.channel FROM search_fts f
                        LEFT JOIN evidence e ON e.evidence_id=f.source_id
                        JOIN asset a ON a.asset_id=f.asset_id
                        WHERE search_fts MATCH ? AND a.available_at<=?
                          AND (e.source_id IS NULL OR e.available_at<=?)
                          AND (e.source_id IS NULL OR NOT EXISTS (
                            SELECT 1 FROM evidence revision
                            WHERE revision.asset_id=e.asset_id
                              AND revision.supersedes_source_id=e.source_id
                              AND revision.available_at<=?
                          ))
                        """,
                        (
                            expression,
                            as_of.isoformat(),
                            as_of.isoformat(),
                            as_of.isoformat(),
                        ),
                    ).fetchall()
                    identity_text_assets = {
                        row["asset_id"] for row in matches if row["channel"] == "identity"
                    }
                    evidence_text_assets = {
                        row["asset_id"] for row in matches if row["channel"] == "evidence"
                    }
        hits = []
        weak_match_count = 0
        for row in rows:
            text_assets = (identity_text_assets or set()) | (evidence_text_assets or set())
            if identity_text_assets is not None and row["asset_id"] not in text_assets:
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
            channels = []
            score = 0
            if row["asset_id"] in (identity_text_assets or set()):
                channels.append("identity_text")
                score += 3
            if row["asset_id"] in (evidence_text_assets or set()):
                channels.append("evidence_text")
                confirmed.append(f"text:{query.text}")
                score += 18
            score += sum(25 if marker.startswith("sector:") else 8 for marker in confirmed)
            score += sum(30 for marker in confirmed if marker.startswith("event:"))
            score -= len(contradicted) * 20
            if row["instrument_type"] == "fund":
                score -= 40
            sufficient = bool(
                identity_text_assets is None
                or row["asset_id"] in (evidence_text_assets or set())
                or any(marker.startswith(("sector:", "event:")) for marker in confirmed)
            )
            if not sufficient:
                weak_match_count += 1
                continue
            hits.append(
                CandidateHit(
                    identity=AssetIdentity.model_validate_json(row["identity_json"]),
                    score=score,
                    confirmed=confirmed,
                    contradicted=contradicted,
                    unknown=unknown,
                    evidence_source_ids=sorted(item["source_id"] for item in evidence)[:8],
                    retrieval_channels=channels,
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
        tied_top = bool(
            query.require_unique_top and len(hits) > 1 and hits[0].score == hits[1].score
        )
        return CandidateBatch(
            status="ok" if hits and not tied_top else "unresolved",
            candidates=hits[:limit],
            full_universe_size=coverage["indexed_assets"],
            visible_universe_size=coverage["visible_assets"],
            matched_before_limit=len(hits),
            limit=limit,
            index_payload_sha256=self.manifest.payload_sha256,
            weak_match_count=weak_match_count,
            coverage_warnings=(
                ["ambiguous_top_score"]
                if tied_top
                else []
                if hits
                else ["no_candidate_with_sufficient_evidence"]
            ),
        )

    def evidence(self, identity, *, as_of, kinds):
        identity = canonicalize_identity(identity)
        try:
            asset_id = stable_asset_id(identity)
        except ValueError:
            return {"status": "unavailable", "records": []}
        with self._connect() as connection:
            placeholders = ",".join("?" for _ in kinds)
            rows = connection.execute(
                f"""SELECT e.* FROM evidence e
                WHERE e.asset_id=? AND e.available_at<=? AND e.kind IN ({placeholders})
                  AND NOT EXISTS (
                    SELECT 1 FROM evidence revision
                    WHERE revision.asset_id=e.asset_id
                      AND revision.supersedes_source_id=e.source_id
                      AND revision.available_at<=?
                  )
                ORDER BY e.available_at,e.source_id""",
                (asset_id, as_of.isoformat(), *sorted(kinds), as_of.isoformat()),
            ).fetchall()
        return {
            "status": "ok" if rows else "unavailable",
            "records": [dict(row) for row in rows],
            "as_of": as_of.isoformat(),
        }

    def detective_evidence(self, identity, *, as_of):
        identity = canonicalize_identity(identity)
        try:
            asset_id = stable_asset_id(identity)
        except ValueError:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT e.record_json FROM evidence e
                WHERE e.asset_id=? AND e.available_at<=?
                  AND NOT EXISTS (
                    SELECT 1 FROM evidence revision
                    WHERE revision.asset_id=e.asset_id
                      AND revision.supersedes_source_id=e.source_id
                      AND revision.available_at<=?
                  )
                ORDER BY e.available_at,e.source_id""",
                (asset_id, as_of.isoformat(), as_of.isoformat()),
            ).fetchall()
        return [json.loads(row["record_json"]) for row in rows]
