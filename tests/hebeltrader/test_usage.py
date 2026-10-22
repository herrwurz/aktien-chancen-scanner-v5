import json

import pytest

from scanner.hebeltrader.usage import append_usage, verify_usage


def test_usage_hash_chain_and_no_credentials(tmp_path):
    path = tmp_path / "usage.jsonl"
    first = append_usage(path, dict(status="started", cost_eur=None))
    second = append_usage(path, dict(status="error", attempted_requests=3, cost_eur=None))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[1]["previous_sha256"] == first
    assert verify_usage(path) == second
    before = path.read_bytes()
    with pytest.raises(ValueError):
        append_usage(path, dict(api_token="never-store"))
    assert path.read_bytes() == before
    path.write_bytes(before.replace(b'"attempted_requests":3', b'"attempted_requests":0'))
    with pytest.raises(ValueError, match="integrity"):
        append_usage(path, dict(status="completed"))


def test_collect_cli_logs_bounded_failure_without_token_or_paid_network(tmp_path, monkeypatch):
    import httpx

    from scanner.hebeltrader.eodhd import EodhdClient
    from scanner.hebeltrader.historical_cli import main

    monkeypatch.setenv("EODHD_API_TOKEN", "synthetic-secret-never-log")
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429)))
    monkeypatch.setattr(
        "scanner.hebeltrader.historical_cli.EodhdClient",
        lambda root, **options: EodhdClient(root, **options, client=client, sleeper=lambda _: None),
    )
    assert (
        main(
            [
                "collect",
                "--cache-dir",
                str(tmp_path / "cache"),
                "--symbol",
                "SYN.US",
                "--output",
                str(tmp_path / "unused.json"),
                "--allow-network",
                "--authorize-provider-usage",
                "--max-requests",
                "2",
                "--monthly-total-eur",
                "19.99",
            ]
        )
        == 2
    )
    journal = tmp_path / "cache" / "usage.jsonl"
    rows = [json.loads(line)["event"] for line in journal.read_text().splitlines()]
    assert rows[-1]["status"] == "error"
    assert rows[-1]["attempted_requests"] == 2 and rows[-1]["api_units_spent"] == 2
    assert rows[-1]["cost_eur"] is None
    assert "synthetic-secret" not in journal.read_text()
    assert not (tmp_path / "unused.json").exists()
    assert verify_usage(journal)
