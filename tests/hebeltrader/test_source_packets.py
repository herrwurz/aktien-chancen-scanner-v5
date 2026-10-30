import json
from pathlib import Path

from scanner.hebeltrader.detective.source_packets import (
    validate_document,
    validate_packet,
    validate_packet_dir,
)

EXAMPLE = Path("docs/examples/source-packets/SYNTHETIC-EXAMPLE.json")


def test_synthetic_example_packet_validates():
    docs = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert validate_packet(docs) == []
    rows = validate_packet_dir(EXAMPLE.parent)
    ok = [
        row
        for row in rows
        if row["path"].endswith("SYNTHETIC-EXAMPLE.json") and not row["problems"]
    ]
    assert ok


def test_missing_required_field_is_reported():
    problems = validate_document({"company_name": "X"}, index=0)
    assert any("url" in p for p in problems)
    assert validate_packet([]) == ["packet is empty"]
