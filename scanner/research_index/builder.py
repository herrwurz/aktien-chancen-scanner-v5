"""Deterministic, atomic SQLite/FTS5 research-index builder."""

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from pydantic import BaseModel

from scanner.news import NewsItem
from scanner.research import AssetIdentity, CompanyEvent, CompanyFact, EvidenceRecord

SCHEMA_VERSION = 1


class IndexManifest(BaseModel):
    schema_version: int
    payload_sha256: str
    database_sha256: str
    counts: dict[str, int]


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _asset_id(identity):
    for kind in ("cik", "isin", "wkn", "lei"):
        value = getattr(identity, kind)
        if value:
            return f"{kind}:{value}"
    return f"name:{_sha(identity.name.encode())}"


def _available(identity):
    value = identity.source_available_at or identity.retrieved_at
    return value.isoformat() if value else None


def _records(values, model):
    return [model.model_validate(value) for value in values]


def build_index(path, *, assets, events, facts, news):
    path = Path(path)
    normalized_assets = _records(assets, AssetIdentity)
    normalized_events = _records(events, CompanyEvent)
    normalized_facts = _records(facts, CompanyFact)
    normalized_news = _records(news, NewsItem)
    payload = {
        "assets": sorted(
            (row.model_dump(mode="json") for row in normalized_assets), key=_canonical
        ),
        "events": sorted(
            (row.model_dump(mode="json") for row in normalized_events), key=_canonical
        ),
        "facts": sorted((row.model_dump(mode="json") for row in normalized_facts), key=_canonical),
        "news": sorted((row.model_dump(mode="json") for row in normalized_news), key=_canonical),
    }
    payload_sha = _sha(_canonical(payload))
    counts = {key: len(value) for key, value in payload.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary)
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE asset(
              asset_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL, name TEXT NOT NULL,
              ticker TEXT, cik TEXT, isin TEXT, wkn TEXT, lei TEXT, country TEXT, sector TEXT,
              instrument_type TEXT NOT NULL, available_at TEXT
            );
            CREATE INDEX asset_cik ON asset(cik);
            CREATE INDEX asset_isin ON asset(isin);
            CREATE INDEX asset_wkn ON asset(wkn);
            CREATE TABLE evidence(
              evidence_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
              asset_id TEXT NOT NULL REFERENCES asset(asset_id), kind TEXT NOT NULL,
              event_type TEXT, available_at TEXT NOT NULL, title TEXT NOT NULL,
              record_json TEXT NOT NULL, supersedes_source_id TEXT
            );
            CREATE INDEX evidence_asset_time ON evidence(asset_id, available_at);
            CREATE VIRTUAL TABLE search_fts USING fts5(
              asset_id UNINDEXED, source_id UNINDEXED, channel UNINDEXED, content
            );
            """
        )
        identities = {}
        for identity in sorted(normalized_assets, key=lambda row: _asset_id(row)):
            asset_id = _asset_id(identity)
            identities[asset_id] = identity
            connection.execute(
                "INSERT INTO asset VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    asset_id,
                    identity.model_dump_json(),
                    identity.name,
                    identity.ticker,
                    identity.cik,
                    identity.isin,
                    identity.wkn,
                    identity.lei,
                    identity.country,
                    identity.sector,
                    identity.instrument_type,
                    _available(identity),
                ),
            )
            connection.execute(
                "INSERT INTO search_fts(asset_id,source_id,channel,content) VALUES(?,?,?,?)",
                (
                    asset_id,
                    f"identity:{asset_id}",
                    "identity",
                    " ".join(filter(None, [identity.name, identity.ticker])),
                ),
            )
        lookup = {}
        for asset_id, identity in identities.items():
            for kind in ("cik", "isin", "wkn", "lei"):
                value = getattr(identity, kind)
                if value:
                    lookup[(kind, value)] = asset_id

        def add_evidence(
            source_id,
            identity,
            kind,
            event_type,
            available_at,
            title,
            record,
            supersedes_source_id=None,
        ):
            asset_id = _asset_id(identity)
            if asset_id not in identities or available_at is None:
                return
            evidence_id = f"{source_id}|{asset_id}"
            connection.execute(
                "INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    evidence_id,
                    source_id,
                    asset_id,
                    kind,
                    event_type,
                    available_at.isoformat(),
                    title,
                    record.model_dump_json(),
                    supersedes_source_id,
                ),
            )
            connection.execute(
                "INSERT INTO search_fts(asset_id,source_id,channel,content) VALUES(?,?,?,?)",
                (asset_id, evidence_id, "evidence", title),
            )

        for row in sorted(normalized_events, key=lambda value: value.event_id):
            add_evidence(
                row.event_id,
                row.asset,
                "event",
                row.category,
                row.evidence.source_available_at or row.retrieved_at,
                row.headline,
                row.evidence.model_copy(
                    update={"facts": dict(row.evidence.facts, events=[row.category])}
                ),
            )
        for row in sorted(normalized_facts, key=lambda value: value.fact_id):
            add_evidence(
                row.fact_id,
                row.asset,
                "fact",
                row.claim,
                row.source_available_at or row.retrieved_at,
                f"{row.metric} {row.claim}",
                EvidenceRecord(
                    source_id=row.fact_id,
                    url=row.source_url,
                    title=f"{row.metric}: {row.claim}",
                    published_at=row.published_at,
                    retrieved_at=row.retrieved_at,
                    effective_at=row.published_at,
                    source_available_at=row.source_available_at,
                    source_kind="regulatory",
                    facts={"fact_claims": [row.claim]},
                    content_sha256=row.content_sha256,
                ),
                row.supersedes_fact_id,
            )
        for row in sorted(normalized_news, key=lambda value: value.source_id):
            matched = {
                lookup[(kind, identifier)]
                for kind, values in row.company_identifiers.items()
                for identifier in values
                if (kind, identifier) in lookup
            }
            for asset_id in sorted(matched):
                add_evidence(
                    row.source_id,
                    identities[asset_id],
                    "news",
                    row.event_type,
                    row.source_available_at,
                    row.title,
                    EvidenceRecord(
                        source_id=row.source_id,
                        url=row.url,
                        title=row.title,
                        published_at=row.published_at,
                        retrieved_at=row.retrieved_at,
                        effective_at=row.actual_event_at or row.published_at,
                        source_available_at=row.source_available_at,
                        source_kind="issuer" if row.source_type == "PRIMARY" else "news",
                        facts={"events": [row.event_type]},
                        content_sha256=row.content_hash,
                    ),
                    row.revision_of_source_id,
                )
        connection.execute(
            "INSERT INTO metadata VALUES('schema_version',?)", (str(SCHEMA_VERSION),)
        )
        connection.execute("INSERT INTO metadata VALUES('payload_sha256',?)", (payload_sha,))
        connection.execute(
            "INSERT INTO metadata VALUES('counts',?)", (json.dumps(counts, sort_keys=True),)
        )
        connection.commit()
        connection.execute("PRAGMA optimize")
        connection.close()
        database_sha = _sha(temporary.read_bytes())
        manifest = IndexManifest(
            schema_version=SCHEMA_VERSION,
            payload_sha256=payload_sha,
            database_sha256=database_sha,
            counts=counts,
        )
        os.replace(temporary, path)
        manifest_path = path.with_suffix(path.suffix + ".manifest.json")
        manifest_path.write_bytes(_canonical(manifest.model_dump(mode="json")) + b"\n")
        return manifest
    finally:
        temporary.unlink(missing_ok=True)
