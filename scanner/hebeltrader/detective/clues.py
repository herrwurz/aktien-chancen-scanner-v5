import re

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
FINANCIAL_METRIC = re.compile(
    r"\b(?P<metric>umsatz|gewinn|marge|cashflow)\b[^\d%]{0,30}"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%|mrd\.?|mio\.?)",
    re.I,
)
DATE_HINT = re.compile(r"\b(?:Q[1-4]\s+20\d{2}|20\d{2}|\d{1,2}\.\d{1,2}\.20\d{2})\b", re.I)

LEXICONS = {
    "sectors": {
        "healthcare": ("gesundheit", "healthcare", "gesundheitskonzern"),
        "pharma": ("pharma", "medikamente"),
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
        "DE": ("deutscher konzern", "deutsches unternehmen", "dax"),
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
