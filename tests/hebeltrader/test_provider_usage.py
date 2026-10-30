import json
from datetime import UTC, datetime


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("provider body must not escape")

    def json(self):
        return self.payload


def test_tavily_usage_returns_plan_remaining_credits_and_caches():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(
            {
                "key": {"usage": 12, "limit": 1000, "search_usage": 12},
                "account": {
                    "current_plan": "Researcher",
                    "plan_usage": 123,
                    "plan_limit": 1000,
                    "paygo_usage": 0,
                    "paygo_limit": 0,
                },
            }
        )

    monitor = TavilyUsageMonitor(getter=get, clock=lambda: 100)
    first = monitor.snapshot("tvly-private")
    second = monitor.snapshot("tvly-private")

    assert first == second
    assert first == {
        "status": "available",
        "plan": "Researcher",
        "plan_usage": 123,
        "plan_limit": 1000,
        "plan_remaining": 877,
        "key_usage": 12,
        "key_limit": 1000,
        "search_usage": 12,
        "paygo_usage": 0,
        "paygo_limit": 0,
    }
    assert len(calls) == 1
    assert calls[0][0] == "https://api.tavily.com/usage"
    assert calls[0][1]["headers"] == {"Authorization": "Bearer tvly-private"}
    assert calls[0][1]["follow_redirects"] is False


def test_tavily_usage_fails_closed_without_leaking_key():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    def get(*args, **kwargs):
        raise RuntimeError("tvly-private provider body")

    result = TavilyUsageMonitor(getter=get).snapshot("tvly-private")

    assert result == {"status": "unavailable", "reason": "network_error"}
    assert "private" not in json.dumps(result)


def test_tavily_usage_rejects_malformed_numbers():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    result = TavilyUsageMonitor(
        getter=lambda *args, **kwargs: Response(
            {"account": {"plan_usage": "many", "plan_limit": 1000}}
        )
    ).snapshot("key")

    assert result == {"status": "unavailable", "reason": "invalid_response"}


def test_tavily_usage_rejects_fractional_nonfinite_and_missing_values():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    valid_key = {"usage": 1, "limit": 1000, "search_usage": 1}
    valid_account = {
        "current_plan": "Researcher",
        "plan_usage": 1,
        "plan_limit": 1000,
        "paygo_usage": 0,
        "paygo_limit": 0,
    }
    invalid_payloads = [
        {"key": valid_key, "account": {**valid_account, "plan_usage": 1.9}},
        {"key": valid_key, "account": {**valid_account, "plan_usage": float("inf")}},
        {"key": valid_key, "account": {**valid_account, "current_plan": "key"}},
    ]

    for payload in invalid_payloads:
        result = TavilyUsageMonitor(
            getter=lambda *args, payload=payload, **kwargs: Response(payload)
        ).snapshot("key")
        assert result == {"status": "unavailable", "reason": "invalid_response"}


def test_tavily_usage_preserves_missing_optional_values_as_unknown():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    result = TavilyUsageMonitor(
        getter=lambda *args, **kwargs: Response(
            {
                "account": {
                    "current_plan": "Researcher",
                    "plan_usage": 25,
                    "plan_limit": 1000,
                },
            }
        )
    ).snapshot("key")

    assert result["status"] == "available"
    assert result["plan_remaining"] == 975
    assert result["search_usage"] is None
    assert result["key_usage"] is None
    assert result["key_limit"] is None
    assert result["paygo_usage"] is None
    assert result["paygo_limit"] is None


def test_tavily_usage_accepts_documented_nested_objects():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    result = TavilyUsageMonitor(
        getter=lambda *args, **kwargs: Response(
            {
                "key": {"key": {"usage": 7, "limit": 1000, "search_usage": 7}},
                "account": {
                    "account": {
                        "current_plan": "Researcher",
                        "plan_usage": 7,
                        "plan_limit": 1000,
                        "paygo_usage": 0,
                        "paygo_limit": 0,
                    }
                },
            }
        )
    ).snapshot("key")

    assert result["status"] == "available"
    assert result["plan_remaining"] == 993


def test_tavily_usage_reports_safe_http_reason_without_response_body():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    for status, reason in [
        (401, "authentication_failed"),
        (403, "access_forbidden"),
        (429, "rate_limited"),
        (503, "provider_unavailable"),
    ]:
        result = TavilyUsageMonitor(
            getter=lambda *args, status=status, **kwargs: Response(
                {"detail": "tvly-private must never escape"}, status_code=status
            )
        ).snapshot("tvly-private")
        assert result == {"status": "unavailable", "reason": reason}
        assert "private" not in json.dumps(result)


def test_openai_usage_sums_valid_archives_and_ignores_malformed_files(tmp_path):
    from scanner.hebeltrader.detective.provider_usage import summarize_openai_usage

    root = tmp_path / "audit"
    root.mkdir()
    recorded_at = datetime.now(UTC).isoformat()
    (root / "api-one.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": recorded_at,
                "request": {"model": "gpt-4.1-mini-2025-04-14"},
                "response": {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
            }
        )
    )
    (root / "api-two.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": recorded_at,
                "request": {"model": "gpt-4.1-2025-04-14"},
                "response": {"usage": {"input_tokens": 250, "output_tokens": 100}},
            }
        )
    )
    (root / "api-search.json").write_text(
        json.dumps(
            {
                "provider": "search",
                "recorded_at": recorded_at,
                "response": {"usage": {"credits": 9}},
            }
        )
    )
    (root / "api-unknown-model.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": recorded_at,
                "request": {"model": "retired-unknown-model"},
                "response": {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
            }
        )
    )
    (root / "api-broken.json").write_text("not-json")
    (root / "api-array.json").write_text("[]")
    (root / "api-bad-time.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": datetime.now(UTC).strftime("%Y-%m") + "garbage",
                "response": {"usage": {"prompt_tokens": 9000, "completion_tokens": 9000}},
            }
        )
    )
    (root / "api-partial.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": recorded_at,
                "response": {"usage": {"prompt_tokens": 9000}},
            }
        )
    )
    (root / "api-fractional.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": recorded_at,
                "response": {"usage": {"prompt_tokens": 12.5, "completion_tokens": 4}},
            }
        )
    )
    (root / "api-old.json").write_text(
        json.dumps(
            {
                "provider": "ai",
                "recorded_at": "2020-01-01T00:00:00+00:00",
                "response": {"usage": {"prompt_tokens": 9000, "completion_tokens": 9000}},
            }
        )
    )

    assert summarize_openai_usage(root) == {
        "status": "estimated",
        "model": "mixed",
        "month": datetime.now(UTC).strftime("%Y-%m"),
        "input_tokens": 1260,
        "output_tokens": 605,
        "estimated_usd": None,
        "pricing_complete": False,
        "models": [
            {
                "model": "gpt-4.1-2025-04-14",
                "input_tokens": 250,
                "output_tokens": 100,
                "estimated_usd": 0.0013,
                "pricing_status": "known",
            },
            {
                "model": "gpt-4.1-mini-2025-04-14",
                "input_tokens": 1000,
                "output_tokens": 500,
                "estimated_usd": 0.0012,
                "pricing_status": "known",
            },
            {
                "model": "retired-unknown-model",
                "input_tokens": 10,
                "output_tokens": 5,
                "estimated_usd": None,
                "pricing_status": "unknown",
            },
        ],
        "balance_available_via_project_key": False,
    }


def test_tavily_paygo_without_plan_limit_is_available():
    from scanner.hebeltrader.detective.provider_usage import TavilyUsageMonitor

    payload = {
        "key": {"usage": 5, "limit": None, "search_usage": 5},
        "account": {
            "current_plan": "Pay as you go",
            "plan_usage": 40,
            "plan_limit": None,
            "paygo_usage": 40,
            "paygo_limit": None,
        },
    }
    result = TavilyUsageMonitor(getter=lambda *a, **k: Response(payload)).snapshot("tvly-x")
    assert result["status"] == "available"
    assert result["plan_remaining"] is None and result["paygo_usage"] == 40
