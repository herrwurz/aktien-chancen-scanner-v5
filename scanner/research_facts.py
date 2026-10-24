"""Deterministic, deliberately narrow extraction of comparable SEC XBRL facts."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from scanner.research import AssetIdentity, CompanyFact

SUPPORTED = {
    "NetIncomeLoss": "net_income",
    "Revenues": "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
}


def _at(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def extract_sec_company_facts(record, identity: AssetIdentity, *, availability_by_accession=None):
    payload = record["payload"]
    retrieved = _at(record["retrieved_at"])
    source_url = record["source_reference"]
    availability_by_accession = availability_by_accession or {}

    def available_at(row):
        return availability_by_accession.get(row["accn"]) or _at(
            row["filed"] + "T23:59:59.999999+00:00"
        )

    result = []
    for namespace, concepts in payload.get("facts", {}).items():
        if namespace != "us-gaap" or not isinstance(concepts, dict):
            continue
        for concept, detail in concepts.items():
            metric = SUPPORTED.get(concept)
            if metric is None:
                continue
            for unit, rows in detail.get("units", {}).items():
                eligible = [
                    row
                    for row in rows
                    if row.get("form") in {"10-Q", "10-K"}
                    and all(
                        row.get(key) is not None
                        for key in ("val", "start", "end", "filed", "accn", "fy", "fp")
                    )
                ]
                eligible.sort(key=lambda row: (row["end"], row["filed"], row["accn"]))
                for index, row in enumerate(eligible):
                    current_available_at = available_at(row)
                    prior = None
                    for candidate in reversed(eligible[:index]):
                        if (
                            candidate["fp"] == row["fp"]
                            and int(candidate["fy"]) == int(row["fy"]) - 1
                            and candidate["start"][5:] == row["start"][5:]
                            and candidate["end"][5:] == row["end"][5:]
                            and available_at(candidate) <= current_available_at
                        ):
                            prior = candidate
                            break
                    value = Decimal(str(row["val"]))
                    claim = "reported_value"
                    verification = "unknown"
                    if prior is not None:
                        comparison = Decimal(str(prior["val"]))
                        claim = (
                            "year_over_year_increase"
                            if value > comparison
                            else "year_over_year_decrease"
                            if value < comparison
                            else "unchanged"
                        )
                        verification = "source_verified"
                    else:
                        comparison = None
                    filed = current_available_at
                    token = f"{identity.cik}:{concept}:{unit}:{row['accn']}"
                    result.append(
                        CompanyFact(
                            fact_id="sec-fact:" + hashlib.sha256(token.encode()).hexdigest(),
                            asset=identity,
                            metric=metric,
                            claim=claim,
                            value=value,
                            unit=unit,
                            period_start=row["start"],
                            period_end=row["end"],
                            comparison_value=comparison,
                            comparison_period_start=prior.get("start") if prior else None,
                            comparison_period_end=prior.get("end") if prior else None,
                            source_url=source_url,
                            source_location=(
                                f"/facts/{namespace}/{concept}/units/{unit}/{rows.index(row)}"
                            ),
                            published_at=filed,
                            source_available_at=filed,
                            retrieved_at=retrieved,
                            extraction_method="sec_xbrl_exact_duration_fiscal_period_v1",
                            verification_status=verification,
                            content_sha256=record["raw_sha256"],
                        )
                    )
    return result
