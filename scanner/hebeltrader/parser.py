import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

from scanner.hebeltrader.calculations import calculate_crv
from scanner.hebeltrader.domain import Extraction, RecommendationData
from scanner.hebeltrader.pdf import read_pdf

HEADER = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*[·•]?\s*#\s*(\d+)\s*/\s*(\d{4})")
PRODUCT = re.compile(
    r"(?:Optionsschein(?:[ -]+(?:Call|Put))?|(?:Call|Put)[ -]+Optionsschein|"
    r"Turbo(?:[ -]+Unlimited)?(?:[ -]+(?:Long|Short))?|"
    r"(?:Knock[ -]?Out|Faktor[ -]?Zertifikat|Hebelzertifikat)(?:[ -]+(?:Long|Short))?)",
    re.I,
)
NUMBER = re.compile(r"^(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")


def parse_number(value):
    token = re.sub(r"\s*(?:€|EUR|USD|\$|GBP|%|x|×)\s*$", "", value.strip())
    if not NUMBER.fullmatch(token):
        raise ValueError("Ambiguous or invalid German decimal")
    number = Decimal(token.replace(".", "").replace(",", "."))
    if number > Decimal("1e18"):
        raise ValueError("Number exceeds supported range")
    return number


def parse_date(value):
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError("Invalid date")


def isin(value):
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", value):
        raise ValueError("Invalid ISIN")
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = sum(
        (int(c) * 2 // 10 + int(c) * 2 % 10) if i % 2 else int(c)
        for i, c in enumerate(reversed(digits))
    )
    if total % 10:
        raise ValueError("Invalid ISIN checksum")
    return value


def add(rec, field, raw, line, convert=str, rule="label-v1"):
    rec.evidence.setdefault(field, []).append(
        dict(
            page=line["page"],
            bbox=line["bbox"],
            raw=raw,
            text=line["text"],
            rule=rule,
        )
    )
    try:
        value = convert(raw.strip())
    except ValueError:
        rec.flags.append(dict(code="invalid_value", field=field, page=line["page"]))
        rec.values[field] = None
        return
    previous = rec.values.get(field)
    if any(
        f["field"] == field and f["code"] in ("invalid_value", "conflicting_values")
        for f in rec.flags
    ):
        return
    if previous is not None and previous != value:
        rec.values[field] = None
        rec.flags.append(dict(code="conflicting_values", field=field, page=line["page"]))
    else:
        rec.values[field] = value


def parse_fields(rec, lines, stock=False):
    prefix = "stock" if stock else "derivative"
    rules = [
        (
            r"WKN\s+(.+)",
            prefix + "_wkn",
            lambda s: s if re.fullmatch(r"[A-HJ-NP-Z0-9]{6}", s) else _invalid(),
        ),
        (r"ISIN\s+(.+)", prefix + "_isin", isin),
        (
            r"(?:Akt\.?\s*Kurs\s*\*{0,2}|Aktueller Kurs|Einstiegskurs)\s*:?\s+(.+)",
            "stock_price" if stock else "entry_price",
            parse_number,
        ),
        (r"(?:Kursziel|Ziel)\s*([12])\s+(.+)", None, parse_number),
        (r"Stopp?\s*([12])\s+(.+)", None, parse_number),
        (r"Emittent\s*:?\s+(.+)", "issuer", str),
        (r"Basispreis\s+(.+)", "strike", parse_number),
        (r"(?:Omega/Hebel|Omega|Hebel)\s+(.+)", "omega", parse_number),
        (r"(?:Laufzeit|Fälligkeit)\s+(.+)", "maturity_date", parse_date),
        (r"CRV\s*:?\s*(.+)", "crv", parse_number),
    ]
    for i, line in enumerate(lines):
        text = unicodedata.normalize("NFKC", line["text"]).replace("\u00ad", "").strip()
        open_end = re.fullmatch(
            r"(?:(?:Laufzeit|Fälligkeit)\s*:?\s*)?(?:open[ -]*end|unbefristet|unbegrenzt)",
            text,
            re.I,
        )
        if open_end:
            add(rec, "term_text", text, line, lambda _: "open end", "explicit-open-end-v21")
            continue
        if text in ("Laufzeit", "Fälligkeit"):
            for neighbor in lines[max(0, i - 1) : i + 2]:
                if re.fullmatch(r"\d{2}\.\d{2}\.\d{2,4}", neighbor["text"]):
                    add(
                        rec,
                        "maturity_date",
                        neighbor["text"],
                        neighbor,
                        parse_date,
                        "adjacent-date-v1",
                    )
        if re.fullmatch(r"[\d., /½]+\s*(?:Monate?|Jahre?)", text):
            add(rec, "term_text", text, line)
        if text.startswith("Basiswert "):
            add(rec, "stock_name", text.removeprefix("Basiswert "), line)
        if re.search(r"Kursindikation.*Stand:", text):
            add(rec, "quote_as_of_text", text, line)
        if re.match(r"Fundamentaler Hinweis:", text):
            add(rec, "fundamental_notes", text.split(":", 1)[1].strip(), line)
        if re.match(r"Technischer Hinweis:", text):
            add(rec, "technical_notes", text.split(":", 1)[1].strip(), line)
        for pattern, field, converter in rules:
            match = re.fullmatch(pattern, text, re.I)
            if not match:
                continue
            if field is None:
                kind = "stop" if text.lower().startswith("stop") else "target"
                field = prefix + "_" + kind + match[1]
                raw = match[2]
            else:
                raw = match[1]
            add(rec, field, raw, line, converter)
            if field in ("entry_price", "stock_price", "strike"):
                currency = re.search(r"(EUR|€|USD|\$|GBP)\s*$", raw)
                if currency:
                    add(
                        rec,
                        "strike_currency" if field == "strike" else prefix + "_currency",
                        {"€": "EUR", "$": "USD"}.get(currency[1], currency[1]),
                        line,
                    )
            if field == "omega":
                add(rec, "omega_label", text[: match.start(1)].strip(), line)
            if field == "entry_price":
                add(
                    rec,
                    "entry_kind",
                    "recommended_entry" if text.lower().startswith("einstieg") else "indication",
                    line,
                )


def product_heading(lines, index):
    text = unicodedata.normalize("NFKC", lines[index]["text"]).strip()
    consumed = 1
    if re.fullmatch(r"Turbo(?: Unlimited)?", text, re.I) and index + 1 < len(lines):
        direction = lines[index + 1]["text"].strip()
        if re.fullmatch(r"Long|Short", direction, re.I):
            text += " " + direction
            consumed = 2
    if not PRODUCT.fullmatch(text):
        return None
    nearby = lines[index + consumed : index + consumed + 16]
    if not any(re.match(r"(?:WKN|ISIN)\b", row["text"], re.I) for row in nearby):
        return None
    if not any(
        re.match(r"(?:Akt\.?\s*Kurs|Aktueller Kurs|Einstiegskurs)\b", row["text"], re.I)
        for row in nearby
    ):
        return None
    return text.title(), consumed, text


def prose_crv(rec, page):
    number = r"(\d[\d.,]*)(?=\s|$|[!;:?)])"
    patterns = [
        r"\(CRV\)\s*(?:von|:|=)?\s*" + number,
        r"\(CRV\)\s+für\s+den\s+empfohlenen\s+Derivate[-\s]*Trade\s+" + number,
        r"Chance[-\s]*Risiko[-\s]*Verhältnis\s+(?:von|:)\s*" + number,
    ]
    for lines in page["regions"]:
        text = " ".join(row["text"] for row in lines)
        offsets = []
        pos = 0
        for row in lines:
            offsets.append((pos, pos + len(row["text"]), row))
            pos += len(row["text"]) + 1
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                source = [
                    row
                    for start, end, row in offsets
                    if start < match.end() and end > match.start()
                ]
                bbox = [
                    min(r["bbox"][0] for r in source),
                    min(r["bbox"][1] for r in source),
                    max(r["bbox"][2] for r in source),
                    max(r["bbox"][3] for r in source),
                ]
                add(
                    rec,
                    "crv",
                    match[1].removesuffix("."),
                    dict(page=page["number"], bbox=bbox, text=" ".join(r["text"] for r in source)),
                    parse_number,
                    "prose-crv-v21",
                )


def _invalid():
    raise ValueError("Invalid identifier")


def _name(value):
    return re.sub(r"\s+", " ", value.casefold()).strip()


def extract_pdf(data: bytes) -> Extraction:
    result = Extraction(pages=read_pdf(data))
    headers = []
    identities = set()
    for page in result.pages:
        for match in re.finditer(r"#\s*(\d+)\s*/\s*(\d{4})", page["text"]):
            if int(match[1]) > 0:
                identities.add((int(match[1]), int(match[2])))
                result.metadata_evidence.append(
                    dict(page=page["number"], raw=match[0], rule="issue-v1")
                )
        for match in HEADER.finditer(page["text"]):
            result.metadata_evidence.append(
                dict(page=page["number"], raw=match[0], rule="header-v1")
            )
            try:
                headers.append((parse_date(match[1]), int(match[2]), int(match[3])))
            except ValueError:
                result.flags.append(dict(code="invalid_publication_date", page=page["number"]))
    unique = set(headers)
    if len(identities) == 1:
        result.issue_number, result.issue_year = next(iter(identities))
    elif len(identities) > 1:
        result.flags.append(dict(code="metadata_conflict"))
    if len(unique) == 1 and len(identities) == 1 and not result.flags:
        pub, number, year = unique.pop()
        if pub.year == year and number > 0:
            result.publication_date, result.issue_number, result.issue_year = pub, number, year
        else:
            result.flags.append(dict(code="metadata_conflict"))
    elif headers:
        result.flags.append(dict(code="metadata_conflict"))
    else:
        result.flags.append(dict(code="missing_publication_metadata"))
    if not any(p["text"].strip() for p in result.pages):
        result.flags.append(dict(code="ocr_required"))
        return result
    stock_sections = []
    for page in result.pages:
        for lines in page["regions"]:
            products = [i for i in range(len(lines)) if product_heading(lines, i)]
            if products:
                for n, start in enumerate(products):
                    end = products[n + 1] - 1 if n + 1 < len(products) else len(lines)
                    rec = RecommendationData()
                    canonical, consumed, raw = product_heading(lines, start)
                    add(
                        rec,
                        "product_type",
                        raw,
                        lines[start],
                        lambda _, canonical=canonical: canonical,
                        "product-heading-v21",
                    )
                    if start > 0 and not HEADER.search(lines[start - 1]["text"]):
                        add(
                            rec,
                            "stock_name",
                            lines[start - 1]["text"],
                            lines[start - 1],
                            rule="product-heading-v1",
                        )
                    body = lines[start + consumed : end]
                    basis = next(
                        (i for i, row in enumerate(body) if row["text"].startswith("Basiswert ")),
                        None,
                    )
                    if basis is not None:
                        stock_sections.append(body[basis:])
                        body = body[:basis]
                    parse_fields(rec, body)
                    result.recommendations.append(rec)
            elif any(line["text"].startswith("Basiswert ") for line in lines):
                stock_sections.append(lines)
    for lines in stock_sections:
        basis = next(
            line["text"].removeprefix("Basiswert ")
            for line in lines
            if line["text"].startswith("Basiswert ")
        )
        matches = [
            r
            for r in result.recommendations
            if _name(r.values.get("stock_name", "")) == _name(basis)
        ]
        if len(matches) == 1:
            parse_fields(matches[0], lines, stock=True)
        elif not result.recommendations:
            rec = RecommendationData(values={"product_type": "stock"})
            parse_fields(rec, lines, stock=True)
            result.recommendations.append(rec)
        else:
            result.flags.append(dict(code="ambiguous_stock_section", page=lines[0]["page"]))
    if len(result.recommendations) == 1:
        rec = result.recommendations[0]
        for page in result.pages:
            prose_crv(rec, page)
            if "CHARTTECHNISCHES BILD AKTIE" in page["text"] and not rec.values.get(
                "technical_notes"
            ):
                add(
                    rec,
                    "technical_notes",
                    page["text"],
                    dict(
                        page=page["number"],
                        bbox=[0, 0, page["width"], page["height"]],
                        text=page["text"],
                    ),
                    rule="technical-page-v1",
                )
        if not rec.values.get("fundamental_notes") and result.pages:
            page = result.pages[0]
            add(
                rec,
                "source_commentary",
                page["text"],
                dict(
                    page=page["number"],
                    bbox=[0, 0, page["width"], page["height"]],
                    text=page["text"],
                ),
                rule="unclassified-opening-commentary-v1",
            )
    if not result.recommendations:
        result.flags.append(dict(code="unrecognized_layout"))
    for rec in result.recommendations:
        for field in (
            "stock_name",
            "derivative_wkn",
            "stock_wkn",
            "issuer",
            "entry_price",
            "stock_price",
            "strike",
            "maturity_date",
            "omega",
            "crv",
            "derivative_target1",
            "derivative_target2",
            "derivative_stop1",
            "derivative_stop2",
            "stock_target1",
            "stock_target2",
            "stock_stop1",
            "stock_stop2",
        ):
            if field == "maturity_date" and rec.values.get("term_text") == "open end":
                continue
            if rec.values.get(field) is None:
                rec.flags.append(dict(code="missing_field", field=field))
        maturity = rec.values.get("maturity_date")
        if (
            isinstance(maturity, date)
            and result.publication_date
            and maturity < result.publication_date
        ):
            rec.flags.append(dict(code="expired_at_publication", field="maturity_date"))
        if rec.values.get("term_text") == "open end" and maturity is not None:
            rec.values["maturity_date"] = None
            rec.flags.append(dict(code="conflicting_term", field="maturity_date"))
        calculate_crv(rec)
    return result
