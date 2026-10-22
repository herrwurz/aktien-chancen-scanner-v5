"""V1.6 requires all rule types and explicit source-bound human approval."""

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .backtest import Rules


def validate_rules(doc, rec, spec, run_at):
    try:
        if (
            hashlib.sha256(doc.original_pdf).hexdigest() != doc.sha256
            or rec.document_sha != doc.sha256
            or spec["document_sha"] != doc.sha256
            or spec["ordinal"] != rec.ordinal
            or spec["instrument_scope"] != "stock"
            or spec["review_status"] != "approved"
            or spec["requires_manual_review"] is not False
            or not isinstance(spec["reviewer"], str)
            or not spec["reviewer"].strip()
        ):
            raise ValueError
        reviewed = datetime.fromisoformat(spec["reviewed_at"])
        if reviewed.utcoffset() is None or reviewed > run_at:
            raise ValueError
        if Decimal(str(spec["partial_fraction"])) != Decimal("0.5"):
            raise ValueError
        if spec["after_target1"] not in {"entry", "stop2", "unchanged", "target1"}:
            raise ValueError
        sale = spec["target2_sale"]
        if Decimal(str(sale["fraction"])) != Decimal("0.5") or sale["trigger"] != "target2":
            raise ValueError
        loss = spec["conditional_loss_exit"]
        if (
            type(loss["days"]) is not int
            or loss["days"] <= 0
            or loss["unit"] not in {"calendar_days", "trading_sessions"}
            or loss["loss_basis"] not in {"total_position", "remaining_position"}
            or loss["condition"] != "position_in_loss"
            or loss["threshold"] != "at_least"
            or loss["evaluation"] != "completed_close"
            or loss["execution"] != "next_session_open"
            or spec.get("exit_after") is not None
        ):
            raise ValueError
        covered = set()
        time_quotes = []
        for evidence in spec["evidence"]:
            page = next(p for p in doc.pages if p["number"] == evidence["page"])
            quote = evidence["quote"]
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError
            text = page.get("text", "")
            if "region" in evidence:
                if type(evidence["region"]) is not int or evidence["region"] < 0:
                    raise ValueError
                region = page["regions"][evidence["region"]]
                text = " ".join(row["text"] for row in region)
            if " ".join(quote.split()) not in " ".join(text.split()):
                raise ValueError
            covered.update(evidence["fields"])
            if "conditional_loss_exit" in evidence["fields"]:
                time_quotes.append(quote)
        if (
            not {"partial_fraction", "after_target1", "target2_sale", "conditional_loss_exit"}
            <= covered
        ):
            raise ValueError
        literal = " ".join(time_quotes).casefold()
        pattern = (
            r"kalender\s*-?\s*tag" if loss["unit"] == "calendar_days" else r"handels\s*-?\s*tag"
        )
        assumption = not bool(re.search(pattern, literal))
        if assumption and (
            not isinstance(spec.get("time_unit_interpretation"), str)
            or not spec["time_unit_interpretation"].strip()
        ):
            raise ValueError
        audit = dict(
            spec,
            research_assumption=assumption,
            sha256=hashlib.sha256(
                json.dumps(spec, sort_keys=True, default=str).encode()
            ).hexdigest(),
        )
        return (
            Rules(
                after_target1=spec["after_target1"],
                version="1.6",
                loss_after_days=loss["days"],
                loss_unit=loss["unit"],
                loss_basis=loss["loss_basis"],
            ),
            audit,
            None,
        )
    except (KeyError, TypeError, ValueError, InvalidOperation, StopIteration, IndexError):
        return None, None, "unverified_rule_evidence"
