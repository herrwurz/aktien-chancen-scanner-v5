import os
import subprocess
import sys

import httpx

from scanner.hebeltrader.detective.chart_check import fetch_eod_bars
from scanner.hebeltrader.detective.provider_usage import EodhdUsageMonitor, TavilyUsageMonitor


def test_worker_process_exits_without_a_scan():
    completed = subprocess.run(
        [sys.executable, "-m", "scanner.worker", "--once"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
        env={**os.environ, "SCANNER_ARCHIVED": "1"},
    )
    assert completed.returncode == 0
    assert "keinen Scan" in completed.stderr + completed.stdout


def test_archived_container_does_not_call_paid_providers(monkeypatch):
    monkeypatch.setenv("SCANNER_ARCHIVED", "1")

    def forbidden(*args, **kwargs):
        raise AssertionError("paid request")

    assert fetch_eod_bars("AAPL", token="secret", client=httpx) is None
    assert TavilyUsageMonitor(getter=forbidden).snapshot("tvly-secret") == {"status": "archived"}
    assert EodhdUsageMonitor(getter=forbidden).snapshot("eodhd-secret") == {"status": "archived"}


def test_teaser_compose_does_not_pass_paid_credentials():
    from pathlib import Path

    import yaml

    cfg = yaml.safe_load(Path("deploy/teaser/compose.yaml").read_text())
    environment = cfg["services"]["app"]["environment"]
    assert environment["SCANNER_ARCHIVED"] == "1"
    assert environment["DETECTIVE_PUBLIC_ALLOW_NETWORK"] == "false"
    assert "EODHD_API_TOKEN" not in environment
    assert "TAVILY_API_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
