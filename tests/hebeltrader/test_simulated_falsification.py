"""Stufe-3b harness: simulated web yields basis=live_falsification without network."""

from __future__ import annotations

from scanner.hebeltrader.detective.simulated_falsification import (
    run_simulated_live_falsification,
)


def test_simulated_live_falsification_identifies_with_basis(tmp_path):
    report = run_simulated_live_falsification(tmp_path)
    assert report["identification"]["status"] == "identified"
    assert report["identification"]["basis"] == "live_falsification"
    assert report["falsification"]["status"] == "performed"
    assert report["countercandidate_count"] >= 5
    assert report["packet_evidence"]["status"] == "ticker_hypothesis_ready"
    assert report["_harness"]["kind"] == "simulated_live_falsification_v1"
    assert any("cancelled" in q or "denied" in q for q in report["_harness"]["queries"])


def test_simulated_path_does_not_claim_historical_packet(tmp_path):
    report = run_simulated_live_falsification(tmp_path)
    assert report["identification"]["basis"] != "historical_source_packet"
    assert "active_falsification_not_performed" not in report["limitations"]
