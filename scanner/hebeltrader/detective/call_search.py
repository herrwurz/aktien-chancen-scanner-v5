"""Operator Call search for top stock hypotheses (dry-run, never a recommendation)."""

from __future__ import annotations

import re
from datetime import date

from .call_proposal import load_selection_model, propose_calls, score_candidate
from .product_research import research_calls
from .prose_briefing import call_search_prose


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("€", "").replace("$", "").replace(" ", "")
    text = text.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _parse_maturity(value):
    if value is None:
        return None
    text = str(value).strip()
    german = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if german:
        return f"{german.group(3)}-{german.group(2)}-{german.group(1)}"
    return text[:10]


def _normalize_product(raw):
    instrument = str(raw.get("instrument") or raw.get("type") or "call")
    return {
        "wkn": raw.get("wkn"),
        "issuer": raw.get("issuer"),
        "strike": _parse_float(raw.get("strike")),
        "maturity": _parse_maturity(raw.get("maturity")),
        "omega": _parse_float(raw.get("omega")),
        "warrant_px_eur": _parse_float(
            raw.get("warrant_px_eur") or raw.get("ask") or raw.get("price")
        ),
        "crv": _parse_float(raw.get("crv")),
        "ratio": _parse_float(raw.get("ratio")),
        "otm_pct": _parse_float(raw.get("otm_pct")),
        "labeled_months": _parse_float(raw.get("labeled_months")),
        "instrument": instrument,
        "source": raw.get("source"),
        "spot": _parse_float(raw.get("spot")),
    }


def _identity(row):
    return row.get("identity") or {}


def _underlying_rows(report, limit=3):
    rows = []
    for item in (report.get("candidates") or [])[:limit]:
        identity = _identity(item)
        rows.append(
            {
                "name": identity.get("name") or item.get("name"),
                "ticker": identity.get("ticker") or item.get("ticker"),
                "asset_id": item.get("asset_id") or identity.get("asset_id"),
                "wkn": identity.get("wkn"),
            }
        )
    return [row for row in rows if row.get("name") or row.get("ticker")]


def _search_products_for_underlying(web, underlying, *, limit=6):
    """Best-effort public search for classic Call terms; never claims confirmation."""
    if web is None:
        return [], "web_unavailable"
    name = underlying.get("name") or ""
    ticker = underlying.get("ticker") or ""
    query = " ".join(
        part
        for part in (
            ticker,
            name,
            "Call Optionsschein WKN Basispreis Laufzeit Bezugsverhältnis",
        )
        if part
    ).strip()
    products = []
    errors = []
    try:
        hits = web.search(query, limit=limit)
    except Exception as exc:  # noqa: BLE001 - surface provider class only
        return [], type(exc).__name__
    for hit in list(hits or [])[:limit]:
        url = hit.get("url") or ""
        snippet = " ".join(
            str(hit.get(key) or "") for key in ("title", "content", "snippet", "raw_content")
        )
        try:
            document = web.fetch(url) if url else {}
        except Exception as exc:  # noqa: BLE001
            errors.append(type(exc).__name__)
            document = {}
        text = "\n".join(
            part
            for part in (snippet, document.get("text") if isinstance(document, dict) else "")
            if part
        )
        wkn_match = re.search(r"(?i)\bWKN\s*[:=]?\s*([A-Z0-9]{6})\b", text)
        if not wkn_match:
            wkn_match = re.search(r"\b([A-Z0-9]{6})\b", text)
        instrument = "call"
        lowered = text.casefold()
        if "knock" in lowered or "turbo" in lowered or "open end" in lowered:
            instrument = "turbo"
        if "put" in lowered and "call" not in lowered:
            instrument = "put"
        product = {
            "wkn": wkn_match.group(1).upper() if wkn_match else None,
            "issuer": None,
            "strike": None,
            "maturity": None,
            "instrument": instrument,
            "source": {"url": document.get("url") if isinstance(document, dict) else url},
        }
        strike = re.search(
            r"(?i)(?:Basispreis|Strike)\s*[:=]?\s*(\d[\d.,]*)",
            text,
        )
        if strike:
            product["strike"] = strike.group(1)
        maturity = re.search(
            r"(?i)(?:Fälligkeit|Laufzeit|Maturity)\s*[:=]?\s*"
            r"(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})",
            text,
        )
        if maturity:
            product["maturity"] = maturity.group(1)
        omega = re.search(r"(?i)(?:Omega|Hebel)\s*[:=]?\s*(\d[\d.,]*)", text)
        if omega:
            product["omega"] = omega.group(1)
        price = re.search(r"(?i)(?:Brief|Ask|Kurs)\s*[:=]?\s*(\d[\d.,]*)\s*€?", text)
        if price:
            product["warrant_px_eur"] = price.group(1)
        if product["wkn"] or product["strike"] or product["maturity"]:
            products.append(product)
    return products, ("search_errors:" + ",".join(sorted(set(errors))) if errors else None)


def search_calls_for_report(
    report,
    *,
    web=None,
    issuer_domains=None,
    as_of=None,
    enabled=True,
):
    """Search/score Call candidates for the report's top underlyings.

    Dry-run only. Works on hypotheses as well as identified names. Never marks a
    product as the authentic HEBELTRADER call.
    """
    as_of = as_of or date.today().isoformat()
    underlyings = _underlying_rows(report)
    result = {
        "kind": "hebeltrader_call_search_v1",
        "enabled": bool(enabled),
        "dry_run": True,
        "as_of": as_of,
        "status": "disabled",
        "reason": "call_search_disabled",
        "actual_hebeltrader_call_identified": False,
        "is_investment_recommendation": False,
        "underlyings": [],
        "model": load_selection_model().get("kind"),
    }
    if not enabled:
        result["prose"] = call_search_prose(result)
        return result
    if not underlyings:
        result["status"] = "abstain"
        result["reason"] = "no_underlyings"
        result["prose"] = call_search_prose(result)
        return result

    # Prefer issuer-domain research when the stock is already identified.
    issuer_products = []
    if (report.get("identification") or {}).get("status") == "identified":
        researched = research_calls(report, web, issuer_domains or {}, "")
        issuer_products = researched.get("candidates") or []

    blocks = []
    any_ranked = False
    for index, underlying in enumerate(underlyings):
        products = []
        note = None
        if index == 0 and issuer_products:
            products = issuer_products
            note = "issuer_domain_research"
        else:
            products, note = _search_products_for_underlying(web, underlying)
        normalized = [_normalize_product(item) for item in products]
        # Score even for hypotheses: operator provisioning aid, not ID confirmation.
        scored = propose_calls(
            {"identification": {"status": "identified"}},
            normalized,
            as_of=as_of,
            dry_run=True,
            enabled=True,
        )
        proposals = [
            row
            for row in (scored.get("proposals") or [])
            if "non_classic_call" not in (row.get("notes") or [])
        ]
        classic_count = len(proposals)
        if not normalized:
            status = "abstain"
            summary = (
                "Keine öffentlich geparsten Call-Kandidaten."
                if web is not None
                else "Keine Web-Recherche verfügbar — Call-Suche offline abstinent."
            )
            if note:
                summary += f" ({note})"
        elif not proposals:
            status = "abstain"
            summary = (
                f"{len(normalized)} Treffer geprüft, aber keine klassischen Calls im HT-Band "
                "(oft nur Turbos/KOs)."
            )
        else:
            status = "dry_run_ranked"
            any_ranked = True
            best = proposals[0]
            summary = (
                f"{classic_count} klassische Call-Kandidaten gerankt; bester Score "
                f"{best.get('score')} (manuelle Prüfung Pflicht)."
            )
            if note:
                summary += f" Quelle: {note}."
        blocks.append(
            {
                **underlying,
                "status": status,
                "summary": summary,
                "raw_candidate_count": len(normalized),
                "proposals": proposals[:5],
            }
        )

    result["underlyings"] = blocks
    result["status"] = "partial" if any_ranked else "abstain"
    result["reason"] = (
        "scored_against_empirical_call_selection_model" if any_ranked else "no_classic_calls_found"
    )
    result["prose"] = call_search_prose(result)
    return result


def score_supplied_candidates(candidates, *, spot=None, as_of=None):
    """Thin helper for tests/CLI: score already-normalized warrant dicts."""
    bands = load_selection_model().get("bands")
    return [
        {
            **candidate,
            **score_candidate(candidate, spot=spot, as_of=as_of, bands=bands),
        }
        for candidate in candidates
    ]
