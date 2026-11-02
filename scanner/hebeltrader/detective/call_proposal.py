"""Isolated HEBELTRADER-style Call proposal scorer (post-identification only).

Does not alter stock ranking or Investigator scoring. Dry-run by default: ranks
supplied warrant candidates against the empirical selection model and never
emits a trading recommendation or auto-confirmed product identity.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[3] / "docs" / "hebeltrader-call-selection-model.json"

DEFAULT_BANDS = {
    "omega_min": 7.0,
    "omega_prefer_min": 8.0,
    "omega_prefer_max": 13.0,
    "omega_max": 15.0,
    "months_min": 3,
    "months_prefer_min": 4,
    "months_prefer_max": 6,
    "months_max": 10,
    "otm_prefer_min_pct": 10.0,
    "otm_prefer_max_pct": 35.0,
    "price_prefer_min": 0.10,
    "price_prefer_max": 0.50,
    "crv_prefer_min": 12.0,
    "ratio_preferred": 0.1,
}


def load_selection_model(path=None):
    file = Path(path) if path is not None else MODEL_PATH
    if not file.is_file():
        return {"kind": "missing", "bands": dict(DEFAULT_BANDS)}
    payload = json.loads(file.read_text(encoding="utf-8"))
    bands = dict(DEFAULT_BANDS)
    stats = payload.get("empirical_stats") or {}
    omega = stats.get("omega") or {}
    if omega.get("p25") is not None and omega.get("p75") is not None:
        bands["omega_prefer_min"] = float(omega["p25"])
        bands["omega_prefer_max"] = float(omega["p75"])
    crv = stats.get("crv") or {}
    if crv.get("p25") is not None:
        bands["crv_prefer_min"] = float(crv["p25"])
    price = stats.get("warrant_px_eur") or {}
    if price.get("p25") is not None and price.get("p75") is not None:
        bands["price_prefer_min"] = float(price["p25"])
        bands["price_prefer_max"] = float(price["p75"])
    return {"kind": payload.get("kind"), "bands": bands, "path": str(file)}


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text)


def _months_remaining(maturity, as_of):
    mat = _parse_date(maturity)
    start = _parse_date(as_of) or date.today()
    if mat is None:
        return None
    days = (mat - start).days
    if days < 0:
        return None
    return round(days / 30.4375, 1)


def _otm_pct(strike, spot):
    if strike is None or spot is None or spot <= 0:
        return None
    return round((float(strike) / float(spot) - 1.0) * 100.0, 2)


def score_candidate(candidate, *, spot=None, as_of=None, bands=None):
    """Score one classic Call candidate. Higher is closer to publisher pattern."""
    bands = bands or DEFAULT_BANDS
    notes = []
    score = 0.0
    omega = candidate.get("omega")
    months = candidate.get("labeled_months")
    if months is None:
        months = _months_remaining(candidate.get("maturity"), as_of)
    otm = candidate.get("otm_pct")
    if otm is None:
        otm = _otm_pct(candidate.get("strike"), spot if spot is not None else candidate.get("spot"))
    price = candidate.get("warrant_px_eur")
    crv = candidate.get("crv")
    ratio = candidate.get("ratio")
    instrument = (candidate.get("instrument") or "call").casefold()

    if "put" in instrument or "knock" in instrument or "turbo" in instrument:
        notes.append("non_classic_call")
        return {
            "score": -100.0,
            "notes": notes,
            "metrics": {
                "omega": omega,
                "months": months,
                "otm_pct": otm,
                "warrant_px_eur": price,
                "crv": crv,
                "ratio": ratio,
            },
        }

    if omega is None:
        notes.append("omega_missing")
    elif bands["omega_prefer_min"] <= omega <= bands["omega_prefer_max"]:
        score += 30
        notes.append("omega_in_prefer_band")
    elif bands["omega_min"] <= omega <= bands["omega_max"]:
        score += 15
        notes.append("omega_in_outer_band")
    else:
        score -= 10
        notes.append("omega_outside_band")

    if months is None:
        notes.append("tenor_missing")
    elif bands["months_prefer_min"] <= months <= bands["months_prefer_max"]:
        score += 25
        notes.append("tenor_in_prefer_band")
    elif bands["months_min"] <= months <= bands["months_max"]:
        score += 10
        notes.append("tenor_in_outer_band")
    else:
        score -= 10
        notes.append("tenor_outside_band")

    if otm is None:
        notes.append("otm_unknown")
    elif bands["otm_prefer_min_pct"] <= otm <= bands["otm_prefer_max_pct"]:
        score += 20
        notes.append("otm_in_prefer_band")
    elif 0 < otm < 50:
        score += 5
        notes.append("otm_mild")
    elif otm <= 0:
        score -= 5
        notes.append("strike_not_otm")
    else:
        notes.append("otm_deep")

    if price is None:
        notes.append("price_missing")
    elif bands["price_prefer_min"] <= price <= bands["price_prefer_max"]:
        score += 15
        notes.append("price_in_prefer_band")
    elif price < 1.0:
        score += 5
        notes.append("price_retailish")
    else:
        notes.append("price_elevated")

    if crv is None:
        notes.append("crv_missing")
    elif crv >= bands["crv_prefer_min"]:
        score += 20
        notes.append("crv_meets_prefer")
    elif crv >= 10:
        score += 8
        notes.append("crv_ge_10")
    else:
        score -= 5
        notes.append("crv_low")

    if ratio is None:
        notes.append("ratio_missing")
    elif abs(float(ratio) - bands["ratio_preferred"]) < 1e-9:
        score += 5
        notes.append("ratio_preferred")

    return {
        "score": round(score, 2),
        "notes": notes,
        "metrics": {
            "omega": omega,
            "months": months,
            "otm_pct": otm,
            "warrant_px_eur": price,
            "crv": crv,
            "ratio": ratio,
        },
    }


def propose_calls(
    identification_report,
    candidates,
    *,
    spot=None,
    as_of=None,
    model=None,
    dry_run=True,
    enabled=False,
):
    """Rank warrant candidates only when stock ID is secured and ``enabled``.

    Always returns a non-recommendation payload. When ``enabled`` is false (default),
    abstains without scoring so Investigator paths stay unchanged unless explicitly opted in.
    """
    result = {
        "kind": "hebeltrader_call_proposal_v1",
        "enabled": bool(enabled),
        "dry_run": bool(dry_run),
        "status": "disabled",
        "actual_hebeltrader_call_identified": False,
        "is_investment_recommendation": False,
        "proposals": [],
        "reason": "call_proposal_disabled_by_default",
    }
    if not enabled:
        return result

    status = (identification_report or {}).get("identification", {}).get("status")
    if status != "identified":
        result["status"] = "abstain"
        result["reason"] = "stock_not_identified"
        return result

    if not candidates:
        result["status"] = "abstain"
        result["reason"] = "no_candidates_supplied"
        return result

    model = model or load_selection_model()
    bands = model.get("bands") or DEFAULT_BANDS
    ranked = []
    for raw in candidates:
        scored = score_candidate(raw, spot=spot, as_of=as_of, bands=bands)
        ranked.append(
            {
                "wkn": raw.get("wkn"),
                "issuer": raw.get("issuer"),
                "strike": raw.get("strike"),
                "maturity": raw.get("maturity"),
                "score": scored["score"],
                "notes": scored["notes"],
                "metrics": scored["metrics"],
                "verification_status": "manual_review_required",
                "source": raw.get("source"),
            }
        )
    ranked.sort(key=lambda row: row["score"], reverse=True)
    result.update(
        {
            "status": "dry_run_ranked" if dry_run else "manual_review_required",
            "reason": "scored_against_empirical_call_selection_model",
            "model_kind": model.get("kind"),
            "proposals": ranked,
            "needed_corroboration": [
                "official same-product identifiers",
                "issuer terms sheet at Stand Uhr",
                "AT tradability and spread check",
                "independent risk review",
            ],
        }
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run Call proposal scorer. Requires an identified stock report JSON and "
            "a candidates JSON list. Does not trade or confirm HEBELTRADER originals."
        )
    )
    parser.add_argument("--report", type=Path, required=True, help="Identification report JSON")
    parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
        help="JSON list of warrant candidate dicts",
    )
    parser.add_argument("--spot", type=float, default=None)
    parser.add_argument("--as-of", default=None)
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Opt in; without this flag the scorer abstains (safe default).",
    )
    parser.add_argument("--model", type=Path, default=None)
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    if isinstance(candidates, dict):
        candidates = candidates.get("candidates") or []
    model = load_selection_model(args.model) if args.model else load_selection_model()
    payload = propose_calls(
        report,
        candidates,
        spot=args.spot,
        as_of=args.as_of,
        model=model,
        dry_run=True,
        enabled=args.enable,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if payload["status"] != "disabled" or not args.enable else 0


if __name__ == "__main__":
    raise SystemExit(main())
