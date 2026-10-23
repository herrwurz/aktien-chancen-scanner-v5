import re

WKN = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{6})(?![A-Z0-9])", re.I)
ISIN = re.compile(r"(?<![A-Z0-9])([A-Z]{2}[A-Z0-9]{9}[0-9])(?![A-Z0-9])", re.I)
PERCENT = re.compile(r"\b(\d{1,3}(?:[.,]\d+)?)\s*%")


def extract_clues(text):
    normalized = " ".join(text.split())
    return {
        "wkn_fragments": sorted(
            {value.upper() for value in WKN.findall(normalized) if any(c.isdigit() for c in value)}
        ),
        "isins": sorted({value.upper() for value in ISIN.findall(normalized)}),
        "percentages": [value.replace(",", ".") for value in PERCENT.findall(normalized)],
        "normalized_text": normalized,
    }
