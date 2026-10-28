"""Optional issuer-original product research, separate from stock identification."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit


def _hostname(url):
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return None
        return parsed.hostname
    except ValueError:
        return None


def _domains(config):
    domains = {}
    for issuer, value in config.items():
        # Explicit hostnames only: no suffix matching or inferred issuer domains.
        domain = value.lower().strip() if isinstance(value, str) else ""
        if re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain) and "." in domain:
            domains[domain] = issuer
    return domains


def _literal(text, labels, value):
    match = re.search(r"(?im)(?<!\w)(?:" + labels + r")\s*[:=]\s*(" + value + r")(?=\s|$)", text)
    return match.group(1).strip() if match else None


def research_calls(report, web, issuer_domains: dict[str, str], teaser_text: str) -> dict:
    """Research at most three issuer domains and six approved product URLs.

    Extracted strings are unverified terms, never a trading recommendation or
    evidence that a product is the advertised newsletter call. The teaser's
    advertised return is deliberately not used as a product identifier.
    """
    result = {
        "status": "not_identified",
        "candidates": [],
        "actual_hebeltrader_call_identified": False,
        "needed_corroboration": [
            "official same-product identifiers",
            "official underlying identity",
            "explicit original teaser product identifier",
        ],
        "errors": [],
    }
    if report.get("identification", {}).get("status") != "identified":
        result["reason"] = "stock_not_identified"
        return result
    domains = _domains(issuer_domains or {})
    if not domains:
        result["reason"] = "no_approved_official_issuer_domains"
        return result
    candidates = report.get("candidates", [])
    name = candidates[0].get("identity", {}).get("name") if candidates else None
    if not name or web is None:
        result["reason"] = "company_identity_or_web_unavailable"
        return result
    seen = set()
    for domain in list(domains)[:3]:
        query = f"{name} Call Optionsschein Basispreis Laufzeit Bezugsverhältnis site:{domain}"
        try:
            hits = web.search(query, limit=6)
            for hit in list(hits)[:6]:
                url = hit.get("url", "")
                if _hostname(url) not in domains or url in seen or len(seen) >= 6:
                    continue
                seen.add(url)
                try:
                    document = web.fetch(url)
                    final_url = document.get("url", "")
                    if _hostname(final_url) not in domains:
                        result["errors"].append({"url": url, "reason": "unapproved_final_hostname"})
                        continue
                    text = document.get("text", "")
                    product = {
                        "wkn": _literal(text, "WKN", r"[A-Z0-9]{6}"),
                        "isin": _literal(text, "ISIN", r"[A-Z]{2}[A-Z0-9]{9}[0-9]"),
                        "strike": _literal(
                            text, "Basispreis|Strike", r"\d[\d.,]*(?:\s+(?:USD|EUR|CHF|GBP|JPY))?"
                        ),
                        "maturity": _literal(
                            text,
                            "Laufzeit|Fälligkeit|Maturity",
                            r"(?:\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})",
                        ),
                        "ratio": _literal(
                            text, "Bezugsverhältnis|Ratio", r"\d[\d.,]*(?:\s*:\s*\d[\d.,]*)?"
                        ),
                        "issuer": domains[_hostname(final_url)],
                        "verification_status": "manual_review_required",
                        "underlying_verified": False,
                        "source": {
                            "url": final_url,
                            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            "sha256_scope": "fetched_text",
                            "retrieved_at": document.get("retrieved_at"),
                        },
                    }
                    result["candidates"].append(product)
                except Exception as exc:
                    result["errors"].append({"url": url, "reason": type(exc).__name__})
        except Exception as exc:
            result["errors"].append({"query": query, "reason": type(exc).__name__})
    result["status"] = "manual_review_required" if result["candidates"] else "not_identified"
    result["reason"] = (
        "official_product_terms_require_corroboration"
        if result["candidates"]
        else "no_approved_product_originals"
    )
    return result
