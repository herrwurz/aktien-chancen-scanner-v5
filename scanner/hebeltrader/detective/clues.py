import hashlib
import re

from .schemas import AtomicClue

ISIN = re.compile(r"(?<![A-Z0-9])([A-Z]{2}[A-Z0-9]{9}[0-9])(?![A-Z0-9])", re.I)
EXPLICIT_WKN = re.compile(
    r"\b(?P<label>(?:aktien[- ]?)?wkn|call|optionsschein|turbo)\s*[:#-]?\s*"
    r"(?:wkn\s*)?(?P<value>[A-Z0-9]{6})\b",
    re.I,
)
PERCENT = re.compile(r"\b(\d{1,3}(?:[.,]\d+)?)\s*%")
NUMBER_UNIT = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(mrd\.?|mio\.?|millionen?|milliarden?|eur|usd)\b", re.I
)
PERCENT_TOKEN = r"(?:%|prozent)"
PROMO_CUE = r"(?:gewinnchance|rendite|call|optionsschein|potenzial|chance)"
FINANCIAL_METRIC = re.compile(
    rf"\b(?P<metric>umsatz|gewinn|marge|cashflow)\b[^\d%]{{0,30}}"
    rf"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>{PERCENT_TOKEN}|mrd\.?|mio\.?)",
    re.I,
)
FINANCIAL_PERCENT_SENTENCE = re.compile(
    rf"\b(?P<metric>umsatz|gewinn|marge|cashflow)\b(?P<context>[^.!?]{{0,100}}?)"
    rf"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>{PERCENT_TOKEN})",
    re.I,
)
DATE_HINT = re.compile(r"\b(?:Q[1-4]\s+20\d{2}|20\d{2}|\d{1,2}\.\d{1,2}\.20\d{2})\b", re.I)
PROMOTIONAL_RETURN = re.compile(
    rf"(?P<value>\d{{1,3}}(?:\.\d{{3}})+|\d+(?:[,.]\d+)?)\s*{PERCENT_TOKEN}"
    rf"(?=[^.!?]{{0,45}}\b{PROMO_CUE}\b)",
    re.I,
)
PROMOTIONAL_RETURN_PREFIXED = re.compile(
    rf"\b{PROMO_CUE}\b[^.!?]{{0,45}}"
    rf"(?P<value>\d{{1,3}}(?:\.\d{{3}})+|\d+(?:[,.]\d+)?)\s*{PERCENT_TOKEN}",
    re.I,
)

LEXICONS = {
    "sectors": {
        "healthcare": ("gesundheit", "healthcare", "gesundheitskonzern"),
        "pharma": ("pharma", "medikamente"),
        "semiconductors": ("halbleiter", "semiconductor"),
        "medical_technology": ("medizintechnik", "medical technology"),
        "laboratory": ("labor", "laborausrüstung", "life science"),
        "sportswear": ("sportartikel", "sportswear", "sneaker"),
        "energy": ("energie", "energy"),
        "power_grid": ("stromnetz", "netzbetreiber", "power grid"),
        "agriculture_machinery": ("landmaschinen", "traktor", "agrartechnik"),
        "gold_mining": ("goldmine", "goldminen", "goldproduzent"),
        "insurance": ("versicherer", "versicherung", "insurance"),
    },
    "events": {
        "quarterly_results": ("quartalszahlen", "quartalsergebnis", "quarterly results"),
        "dividend_growth": ("dividendenwachstum", "dividende seit", "dividendenaristokrat"),
        "guidance_raise": (
            "prognose angehoben",
            "prognoseanhebung",
            "angehobene prognose",
            "angehobene jahresprognose",
            "angehobenen jahresprognose",
            "guidance raise",
        ),
        "earnings_beat": ("gewinn über erwartung", "ergebnisüberraschung", "earnings beat"),
        "acquisition_or_stake": ("übernahme", "akquisition", "beteiligung", "acquisition"),
        "major_contract": ("großauftrag", "bedeutender auftrag", "major contract"),
        "regulatory_decision": ("zulassung", "regulatorische entscheidung"),
        "management_change": ("managementwechsel", "ceo-wechsel", "vorstandswechsel"),
        "share_buyback": ("aktienrückkauf", "share buyback"),
        "capital_action": ("kapitalmaßnahme", "kapitalerhöhung"),
    },
    "countries": {
        "US": ("us-konzern", "us unternehmen", "us-versicherer", "amerikanisch", "usa"),
        "DE": ("deutscher konzern", "deutsches unternehmen", "deutsches", "dax"),
        "CA": ("kanadisch", "kanada"),
        "EU": ("europäisch", "europäischer", "europäische", "europa"),
    },
    "fact_claims": {
        "net_income_increase": (
            "gewinnanstieg",
            "gewinnsteigerung",
            "steigender gewinn",
            "steigende gewinne",
        ),
        "net_income_decrease": ("gewinnrückgang", "sinkender gewinn"),
        "revenue_increase": ("umsatzanstieg", "umsatzwachstum", "steigender umsatz"),
        "revenue_decrease": ("umsatzrückgang", "sinkender umsatz"),
    },
}


def _phrase_present(text, phrase):
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.I) is not None


def valid_isin(value):
    expanded = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value.upper())
    digits = [int(char) for char in expanded]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        doubled = digit * 2 if index % 2 else digit
        total += doubled // 10 + doubled % 10
    return total % 10 == 0


def extract_clues(text):
    normalized = " ".join(text.split())
    isins = sorted({value.upper() for value in ISIN.findall(normalized)})
    stock_wkn, derivative_wkn = set(), set()
    for match in EXPLICIT_WKN.finditer(normalized):
        value = match.group("value").upper()
        label = match.group("label").casefold()
        if label in {"call", "optionsschein", "turbo"}:
            derivative_wkn.add(value)
        else:
            stock_wkn.add(value)
    structured = {}
    negative = {}
    matched_phrases = set()
    for group, values in LEXICONS.items():
        structured[group], negative[group] = [], []
        for canonical, phrases in values.items():
            for phrase in phrases:
                if not _phrase_present(normalized, phrase):
                    continue
                matched_phrases.add(phrase.casefold())
                negated = re.search(
                    rf"\b(?:kein(?:e|er|en)?|nicht)\s+(?:\w+\s+){{0,2}}{re.escape(phrase)}\b",
                    normalized,
                    re.I,
                )
                destination = negative[group] if negated else structured[group]
                if canonical not in destination:
                    destination.append(canonical)
                break
    return {
        "stock_wkn": sorted(stock_wkn),
        "derivative_wkn": sorted(derivative_wkn),
        "isins": isins,
        "invalid_isins": [value for value in isins if not valid_isin(value)],
        "percentages": [value.replace(",", ".") for value in PERCENT.findall(normalized)],
        "numbers_with_units": [
            {"value": value.replace(",", "."), "unit": unit.casefold()}
            for value, unit in NUMBER_UNIT.findall(normalized)
        ],
        "financial_metrics": [
            {
                "metric": match.group("metric").casefold(),
                "value": match.group("value").replace(",", "."),
                "unit": match.group("unit").casefold(),
            }
            for match in FINANCIAL_METRIC.finditer(normalized)
        ],
        "date_hints": DATE_HINT.findall(normalized),
        "structured": structured,
        "negative": negative,
        "matched_phrases": sorted(matched_phrases),
        "normalized_text": normalized,
    }


def _span_for(position, spans):
    for span in spans:
        if span.start <= position < span.end:
            return span
    return spans[0] if spans else None


def _normalize_percent_value(value: str) -> str:
    """Keep thousand-separated promo figures (1.717) distinct from decimals (18,5)."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
        return value.replace(".", "")
    return value.replace(",", ".")


def _normalize_unit(unit: str | None) -> str:
    normalized = (unit or "%").casefold()
    return "%" if normalized == "prozent" else normalized


def _atomic(category, normalized, match, spans, **values):
    span = _span_for(match.start(), spans)
    source_id = span.source_id if span else "input"
    page = span.page if span else None
    payload = "|".join(
        (source_id, str(page), str(match.start()), str(match.end()), category, normalized)
    )
    return AtomicClue(
        clue_id=hashlib.sha256(payload.encode()).hexdigest(),
        category=category,
        normalized=normalized,
        quote=match.group(0),
        source_id=source_id,
        page=page,
        start=match.start(),
        end=match.end(),
        **values,
    )


def extract_atomic_clues(text, spans):
    """Extract auditable clues while keeping promotional returns out of fundamentals."""
    clues = []
    promotional_ranges = []
    promotional_matches = sorted(
        [*PROMOTIONAL_RETURN.finditer(text), *PROMOTIONAL_RETURN_PREFIXED.finditer(text)],
        key=lambda item: (item.start(), item.end()),
    )
    for match in promotional_matches:
        if any(start <= match.start() and match.end() <= end for start, end in promotional_ranges):
            continue
        value = _normalize_percent_value(match.group("value"))
        promotional_ranges.append((match.start(), match.end()))
        clues.append(
            _atomic(
                "promotional_derivative_return",
                "promotional_derivative_return",
                match,
                spans,
                instrument_scope="promotional",
                value=value,
                unit="percent",
                confidence_class="high",
            )
        )
    financial_matches = list(FINANCIAL_METRIC.finditer(text))
    financial_matches.extend(FINANCIAL_PERCENT_SENTENCE.finditer(text))
    seen_financial = set()
    for match in sorted(financial_matches, key=lambda item: (item.start(), item.end())):
        if any(start <= match.start() < end for start, end in promotional_ranges):
            continue
        key = (match.start(), match.group("metric").casefold(), match.group("value"))
        if key in seen_financial:
            continue
        seen_financial.add(key)
        period_match = DATE_HINT.search(match.group(0))
        clues.append(
            _atomic(
                "financial_metric",
                match.group("metric").casefold(),
                match,
                spans,
                instrument_scope="stock",
                value=_normalize_percent_value(match.group("value")),
                unit=_normalize_unit(match.groupdict().get("unit")),
                period=period_match.group(0) if period_match else None,
                confidence_class="high",
            )
        )
    for match in EXPLICIT_WKN.finditer(text):
        label = match.group("label").casefold()
        scope = "derivative" if label in {"call", "optionsschein", "turbo"} else "stock"
        value = match.group("value").upper()
        clues.append(
            _atomic(
                "identifier",
                f"{scope}_wkn",
                match,
                spans,
                instrument_scope=scope,
                value=value,
                confidence_class="high",
            )
        )
    for match in ISIN.finditer(text):
        value = match.group(1).upper()
        if valid_isin(value):
            clues.append(
                _atomic(
                    "identifier",
                    "stock_isin",
                    match,
                    spans,
                    instrument_scope="stock",
                    value=value,
                    confidence_class="high",
                )
            )
    business_patterns = {
        "technologies": re.compile(r"\b(?:KI|AI|künstliche Intelligenz)\b", re.I),
        "products": re.compile(
            r"\b(?:KI[- ]?Chips?|Halbleiter|Medikamente?|Batterien?|Roboter)\b", re.I
        ),
        "business": re.compile(
            r"\b(?:entwickelt|produziert|betreibt|liefert)\s+[^.!?]{2,60}", re.I
        ),
    }
    for category, pattern in business_patterns.items():
        for match in pattern.finditer(text):
            clues.append(
                _atomic(
                    category,
                    " ".join(match.group(0).casefold().split()),
                    match,
                    spans,
                    instrument_scope="stock",
                    value=" ".join(match.group(0).split()),
                    confidence_class="medium",
                )
            )
    legacy = extract_clues(text)
    for group in legacy["structured"]:
        for polarity, values in (
            ("asserted", legacy["structured"][group]),
            ("negated", legacy["negative"][group]),
        ):
            for value in values:
                phrase_match = None
                for phrase in LEXICONS[group][value]:
                    phrase_match = re.search(re.escape(phrase), text, re.I)
                    if phrase_match:
                        break
                if phrase_match:
                    clues.append(
                        _atomic(
                            group,
                            value,
                            phrase_match,
                            spans,
                            instrument_scope="stock",
                            value=value,
                            polarity=polarity,
                        )
                    )
    return sorted(clues, key=lambda clue: (clue.start, clue.category, clue.clue_id))
