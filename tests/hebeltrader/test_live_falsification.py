"""Live Stufe-3b wiring: approval + key aliases; no real network in CI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.external_research import ApiConfigurationError
from scanner.hebeltrader.detective.live_falsification import build_live_web, main


def test_build_live_web_requires_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    with pytest.raises(ApiConfigurationError, match="approval"):
        build_live_web(tmp_path, approved=False)


def test_build_live_web_accepts_tavily_alias(tmp_path, monkeypatch):
    monkeypatch.delenv("DETECTIVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-from-alias")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DETECTIVE_SOURCE_AI_API_KEY", raising=False)
    monkeypatch.setenv("DETECTIVE_SOURCE_AI_ENABLED", "false")
    web = build_live_web(tmp_path, approved=True, max_requests=5)
    assert web.allow_network is True
    assert web.apis.search_key == "tvly-from-alias"
    assert web.apis.ai_key is None


def test_cli_blocks_without_approval(tmp_path, monkeypatch, capsys):
    teaser = tmp_path / "teaser.txt"
    teaser.write_text("Übernahmen von AlphaPower und BetaLogic.\n", encoding="utf-8")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("DETECTIVE_EXTERNAL_API_APPROVED", raising=False)
    assert main(["--root", str(tmp_path / "out"), "--text-file", str(teaser)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert "approval" in payload["error"].lower()


def test_settings_accept_provider_env_aliases(monkeypatch):
    from scanner.config import Settings

    monkeypatch.delenv("DETECTIVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("DETECTIVE_SOURCE_AI_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-alias-value")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-alias-value")
    settings = Settings(_env_file=None)
    assert settings.detective_search_api_key is not None
    assert settings.detective_search_api_key.get_secret_value() == "tvly-alias-value"
    assert settings.detective_source_ai_api_key is not None
    assert settings.detective_source_ai_api_key.get_secret_value() == "openai-alias-value"


def test_run_live_uses_injected_web(tmp_path, monkeypatch):
    """Ensure analyze path stays packet-free so live_falsification basis remains reachable."""
    from scanner.hebeltrader.detective import live_falsification as mod
    from scanner.hebeltrader.detective.simulated_falsification import (
        SimulatedWeb,
        acquisition_peer_packet,
    )

    docs = acquisition_peer_packet()
    web = SimulatedWeb(docs)
    monkeypatch.setattr(mod, "build_live_web", lambda *a, **k: web)
    report = mod.run_live_falsification(
        tmp_path,
        teaser_text="Übernahmen von AlphaPower und BetaLogic.",
        publication_at=datetime(2026, 10, 28, 12, tzinfo=UTC),
        approved=True,
    )
    assert report["identification"]["basis"] == "live_falsification"
    assert report["_harness"]["kind"] == "live_falsification_v1"
    assert Path(tmp_path).exists()
