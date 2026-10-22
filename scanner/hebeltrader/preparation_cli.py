"""Read-only DB access and exclusive, reproducible private preparation exports."""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from scanner.db import create_db, create_sessions
from scanner.hebeltrader.config import ImportSettings
from scanner.hebeltrader.preparation import build_preparation


def write_bundle(prefix, report):
    prefix = Path(prefix)
    payloads = {
        ".json": report,
        ".rules.draft.json": report["rules_draft"],
        ".identity-input.json": report["identity_input"],
        ".identities.json": report["identities"],
        ".quality.json": report["quality"],
        ".csv": report["results"],
        ".identities.csv": report["identities"],
        ".quality.csv": report["quality"]["documents"],
    }
    prefix.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    streams, created = {}, []
    try:
        for suffix in payloads:
            path = Path(str(prefix) + suffix)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            streams[suffix] = os.fdopen(fd, "w", encoding="utf-8", newline="")
        for suffix, payload in payloads.items():
            stream = streams[suffix]
            if suffix.endswith(".csv"):
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(["document_sha_or_wkn", "ordinal", "priority", "record_json"])
                for row in payload:
                    writer.writerow(
                        [
                            row.get("document_sha", row.get("wkn")),
                            row.get("ordinal"),
                            row.get("priority"),
                            json.dumps(row, sort_keys=True, ensure_ascii=False, default=str),
                        ]
                    )
            else:
                json.dump(
                    payload, stream, sort_keys=True, ensure_ascii=False, indent=2, default=str
                )
                stream.write("\n")
        return created
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        for stream in streams.values():
            stream.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--run-at", required=True)
    parser.add_argument("--expected-count", type=int, default=118)
    parser.add_argument("--identity-sources", type=Path)
    parser.add_argument("--identity-cache", type=Path)
    args = parser.parse_args(argv)
    engine = None
    try:
        sources = json.loads(args.identity_sources.read_text()) if args.identity_sources else []
        if isinstance(sources, dict):
            sources = sources["records"]
        if not isinstance(sources, list):
            raise ValueError("Source records must be a list")
        clock = datetime.fromisoformat(args.run_at)
        engine = create_db(ImportSettings())
        with create_sessions(engine)() as session:
            session.execute(
                text(
                    "SET TRANSACTION READ ONLY"
                    if engine.dialect.name == "postgresql"
                    else "PRAGMA query_only=ON"
                )
            )
            report = build_preparation(
                session,
                run_at=clock,
                source_records=sources,
                identity_cache=args.identity_cache,
                expected_count=args.expected_count,
            )
            write_bundle(args.output_prefix, report)
        print(json.dumps(report["summary"], sort_keys=True))
        return 0 if report["summary"]["count_matches"] else 2
    except Exception as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
