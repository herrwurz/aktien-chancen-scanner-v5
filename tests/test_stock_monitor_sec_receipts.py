from datetime import UTC, datetime

import pytest

from scanner.stock_monitor.sec_receipts import receipts_from_submissions, record_sha256


def record():
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0001234567-26-000001", "0001234567-26-000002"],
                "acceptanceDateTime": ["2026-10-27T16:15:00", "2026-10-27T16:20:00"],
                "form": ["SC 13D/A", "4"],
            }
        }
    }
    return {
        "payload": payload,
        "retrieved_at": "2026-10-27T20:20:00+00:00",
        "raw_sha256": record_sha256(payload),
    }


def test_sec_timezone_and_form_filter():
    result = receipts_from_submissions(record(), cik=1234567, symbol="XYZ")
    assert len(result) == 1
    assert result[0].published_at.astimezone(UTC) == datetime(2026, 10, 27, 20, 15, tzinfo=UTC)
    assert result[0].source_url.endswith("000123456726000001/0001234567-26-000001-index.html")
    result[0].validate(datetime(2026, 10, 27, 20, 21, tzinfo=UTC))


def test_misaligned_rows_fail_closed():
    r = record()
    r["payload"]["filings"]["recent"]["form"].pop()
    with pytest.raises(ValueError, match="Misaligned"):
        receipts_from_submissions(r, cik=1234567, symbol="XYZ")


def test_naive_retrieval_rejected():
    r = record()
    r["retrieved_at"] = "2026-10-27T20:20:00"
    with pytest.raises(ValueError, match="timezone"):
        receipts_from_submissions(r, cik=1234567, symbol="XYZ")
