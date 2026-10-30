"""Batch evidence scan summary over multiple offline packet pilots."""

import json
from datetime import UTC, datetime

from scanner.hebeltrader.detective.evidence_batch import run_batch
from scanner.hebeltrader.eodhd import exclusive

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def _packet_doc(company, ticker, text, *, url_suffix):
    return {
        "company_name": company,
        "ticker": ticker,
        "url": f"https://issuer.example/{url_suffix}",
        "title": f"{company} release",
        "text": text,
        "source_kind": "regulator",
        "published_at": "2026-10-25T12:00:00+00:00",
        "retrieved_at": NOW.isoformat(),
    }


def test_evidence_batch_marks_historical_packet_identification(tmp_path):
    packets = tmp_path / "packets"
    packets.mkdir()
    docs = [
        _packet_doc(
            f"Company {index}",
            f"C{index}",
            f"Company {index} develops instruments.",
            url_suffix=f"c{index}",
        )
        for index in range(5)
    ]
    docs.append(
        _packet_doc(
            "Thermo Fisher Scientific",
            "TMO",
            (
                "On March 24, 2026, the company acquired Clario Holdings, Inc. "
                "On September 1, 2025, the company acquired filtration assets "
                "from Solventum Corporation."
            ),
            url_suffix="tmo",
        )
    )
    exclusive(packets / "HT-DEMO.json", json.dumps(docs).encode())
    inputs = tmp_path / "HT-DEMO.inputs.json"
    exclusive(
        inputs,
        json.dumps(
            {
                "schema_version": 1,
                "evaluation_class": "development_regression",
                "corpus_kind": "development_regression",
                "independent_benchmark": False,
                "cases": [
                    {
                        "case_id": "HT-DEMO",
                        "headline": "Übernahmen",
                        "teaser_text": (
                            "Mit der Übernahme von Clario und der Übernahme von Solventum "
                            "baut der Konzern aus."
                        ),
                        "publication_date": "2026-10-28",
                        "publication_at": NOW.isoformat(),
                    }
                ],
            }
        ).encode(),
    )
    summary = run_batch([inputs], packets=packets, root=tmp_path / "batch-out")
    assert summary["counts"]["cases"] == 1
    assert summary["counts"]["ticker_hypothesis_ready"] == 1
    assert summary["counts"]["identified_from_packet"] == 1
    row = summary["rows"][0]
    assert row["packet_evidence_ticker"] == "TMO"
    assert row["identification_status"] == "identified"
    assert row["identification_basis"] == "historical_source_packet"
    assert row["decision_status"] == "likely_identified"
