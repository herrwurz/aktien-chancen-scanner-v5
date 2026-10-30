"""Safe provider allowance and locally archived usage summaries."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import httpx

MODEL_PRICES_USD_PER_MILLION = {
    "gpt-4.1-mini-2025-04-14": (0.40, 1.60),
    "gpt-4.1-2025-04-14": (2.00, 8.00),
}


class TavilyUsageMonitor:
    """Fetch Tavily account usage without exposing credentials or provider errors."""

    def __init__(self, *, getter=None, clock=monotonic, ttl_seconds=300):
        self.getter = getter or httpx.get
        self.clock = clock
        self.ttl_seconds = ttl_seconds
        self._cached = None

    @staticmethod
    def _count(value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("invalid usage value")
        return value

    @classmethod
    def _optional_count(cls, values, name):
        value = values.get(name)
        return None if value is None else cls._count(value)

    def snapshot(self, api_key):
        if not api_key:
            return {"status": "not_configured"}
        fingerprint = hashlib.sha256(api_key.encode()).hexdigest()
        now = self.clock()
        if self._cached and self._cached[0] == fingerprint and now < self._cached[1]:
            return self._cached[2]
        try:
            response = self.getter(
                "https://api.tavily.com/usage",
                headers={"Authorization": "Bearer " + api_key},
                timeout=10,
                follow_redirects=False,
            )
        except (httpx.HTTPError, RuntimeError):
            return {"status": "unavailable", "reason": "network_error"}
        status = response.status_code
        if status != 200:
            reason = {
                401: "authentication_failed",
                403: "access_forbidden",
                429: "rate_limited",
            }.get(status, "provider_unavailable" if status >= 500 else "request_rejected")
            return {"status": "unavailable", "reason": reason}
        try:
            payload = response.json()
            account = payload["account"]
            key = payload.get("key", {})
            if not isinstance(account, dict) or not isinstance(key, dict):
                raise ValueError("invalid usage response")
            if isinstance(account.get("account"), dict):
                account = account["account"]
            if isinstance(key.get("key"), dict):
                key = key["key"]
            plan = account["current_plan"]
            if not isinstance(plan, str) or not plan.strip() or api_key in plan:
                raise ValueError("invalid usage plan")
            plan_usage = self._count(account["plan_usage"])
            plan_limit = self._optional_count(account, "plan_limit")
            result = {
                "status": "available",
                "plan": plan.strip()[:80],
                "plan_usage": plan_usage,
                "plan_limit": plan_limit,
                "plan_remaining": None if plan_limit is None else max(plan_limit - plan_usage, 0),
                "key_usage": self._optional_count(key, "usage"),
                "key_limit": self._optional_count(key, "limit"),
                "search_usage": self._optional_count(key, "search_usage"),
                "paygo_usage": self._optional_count(account, "paygo_usage"),
                "paygo_limit": self._optional_count(account, "paygo_limit"),
            }
            self._cached = (fingerprint, now + self.ttl_seconds, result)
            return result
        except (KeyError, TypeError, ValueError, OverflowError):
            return {"status": "unavailable", "reason": "invalid_response"}


def summarize_openai_usage(audit_root: Path):
    """Sum current-month token usage archived from successful OpenAI responses."""

    month = datetime.now(UTC).strftime("%Y-%m")
    usage_by_model = {}
    for path in Path(audit_root).glob("api-*.json"):
        try:
            if path.stat().st_size > 2_000_000:
                continue
            row = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict) or row.get("provider") != "ai":
                continue
            recorded_at = datetime.fromisoformat(row["recorded_at"])
            if recorded_at.tzinfo is None or recorded_at.astimezone(UTC).strftime("%Y-%m") != month:
                continue
            usage = row["response"]["usage"]
            if not isinstance(usage, dict):
                continue
            if "input_tokens" in usage and "output_tokens" in usage:
                incoming, outgoing = usage["input_tokens"], usage["output_tokens"]
            elif "prompt_tokens" in usage and "completion_tokens" in usage:
                incoming, outgoing = usage["prompt_tokens"], usage["completion_tokens"]
            else:
                continue
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in (incoming, outgoing)
            ):
                continue
            model = row.get("request", {}).get("model", "legacy_unknown")
            if not isinstance(model, str) or len(model) > 100:
                model = "legacy_unknown"
            values = usage_by_model.setdefault(model, [0, 0])
            values[0] += incoming
            values[1] += outgoing
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    models = []
    known_total = 0.0
    for model in sorted(usage_by_model):
        incoming, outgoing = usage_by_model[model]
        price = MODEL_PRICES_USD_PER_MILLION.get(model)
        estimated = (
            round((incoming * price[0] + outgoing * price[1]) / 1_000_000, 6) if price else None
        )
        if estimated is not None:
            known_total += estimated
        models.append(
            {
                "model": model,
                "input_tokens": incoming,
                "output_tokens": outgoing,
                "estimated_usd": estimated,
                "pricing_status": "known" if price else "unknown",
            }
        )
    input_tokens = sum(row[0] for row in usage_by_model.values())
    output_tokens = sum(row[1] for row in usage_by_model.values())
    pricing_complete = all(row["pricing_status"] == "known" for row in models)
    return {
        "status": "estimated",
        "model": next(iter(usage_by_model), "none") if len(usage_by_model) <= 1 else "mixed",
        "month": month,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": round(known_total, 6) if pricing_complete else None,
        "pricing_complete": pricing_complete,
        "models": models,
        "balance_available_via_project_key": False,
    }
