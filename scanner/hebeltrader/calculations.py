"""Derived quote ratios, explicitly separate from publisher-supplied CRV."""

import re
from decimal import Decimal, InvalidOperation


def _currency(evidence):
    currencies = set()
    for source in evidence:
        match = re.search(r"(EUR|€|USD|\$|GBP)\s*$", source.get("raw", ""))
        if match:
            currencies.add({"€": "EUR", "$": "USD"}.get(match[1], match[1]))
    return next(iter(currencies)) if len(currencies) == 1 else None


def calculate_crv(rec):
    rec.evidence.pop("_calculated_crv", None)
    rec.flags[:] = [f for f in rec.flags if f["code"] != "crv_not_computable"]
    for target in ("derivative_target1", "derivative_target2"):
        fields = ("entry_price", target, "derivative_stop1")
        reason = None
        try:
            if not (rec.values.get("derivative_wkn") or rec.values.get("derivative_isin")):
                raise ValueError("missing_instrument_identity")
            if any(rec.values.get(f) is None or not rec.evidence.get(f) for f in fields):
                raise ValueError("missing_or_conflicting_input")
            currencies = [_currency(rec.evidence[f]) for f in fields]
            if not currencies[0] or any(c != currencies[0] for c in currencies):
                raise ValueError("missing_or_conflicting_currency")
            entry, goal, stop = (Decimal(str(rec.values[f])) for f in fields)
            if not all(n.is_finite() for n in (entry, goal, stop)) or not 0 <= stop < entry < goal:
                raise ValueError("invalid_risk_or_target")
            value = (goal - entry) / (entry - stop)
            rec.evidence.setdefault("_calculated_crv", []).append(
                dict(
                    kind="calculated",
                    target=target,
                    value=str(value),
                    currency=currencies[0],
                    method="(target-entry_price)/(entry_price-derivative_stop1)",
                    method_version="quoted-derivative-target-ratio-v1",
                    inputs={f: str(rec.values[f]) for f in fields},
                    source_evidence={f: rec.evidence[f] for f in fields},
                )
            )
        except (ValueError, InvalidOperation) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "invalid_decimal"
        if reason:
            rec.flags.append(
                dict(code="crv_not_computable", field="crv", target=target, reason=reason)
            )
