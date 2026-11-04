"""General research queries from teaser words only; no historical solution imports."""

import re

from .background_chip import BACKGROUND_CHIP_QUERIES, teaser_wants_background_chip_profit
from .chip_bottleneck import HIDDEN_CHIP_QUERIES, teaser_wants_hidden_chip_bottleneck


def stock_text(text):
    # Product identifiers/advertised returns cannot seed an underlying-stock lookup.
    text = re.sub(r"\bWKN\s*[:=]?\s*[A-Z0-9]{6}\b", "", text, flags=re.I)
    segments = re.split(r"(?<=[.!?])\s+|\n+", text)
    return " ".join(
        s
        for s in segments
        if not re.search(r"optionsschein|\bcall\b|\bderivat\w*|hebel|renditepotenzial", s, re.I)
    ).strip()


SECTORS = (
    (r"halbleiter|\bchip\w*|semiconductor", "semiconductor"),
    (r"landmaschinen\w*|traktor\w*|agrartechnik|agricultural", "agricultural machinery"),
    (r"versicherung\w*|versicherer|insurance", "insurance"),
    (r"pharma\w*|biotech\w*", "pharmaceutical"),
    (r"gesundheit\w*|medizin\w*|healthcare|medtech", "healthcare"),
    (r"rüstung\w*|verteidigung\w*|defen[sc]e|waffen\w*", "defense"),
    (r"strom\w*|energie\w*|versorger|utilit\w*|power grid", "power infrastructure"),
    (r"software\w*", "software"),
    # Avoid false hits like "Handelsstrategie" / "Handelstag" — require retail issuer cues.
    # Optional hyphen/space so "Handels-Gigant" (HT-003) still matches.
    (
        r"einzelhandel\w*|retail\w*|handels[\s-]*(?:gigant|riese|konzern|unternehmen)\w*|"
        r"supermärkte?\b|warenhaus\w*|großhandel\w*|discounter\w*",
        "retail",
    ),
    (r"kapitalbasis|kernkapital|\bcet\s*1\b|harte[rn]?\s+kernkapital", "banks"),
    # Issuer cues only. "Finanzrevolution" and "finanzstark" are not a sector,
    # and "Datenbank" must not count as a bank.
    (
        r"finanz(?:schwergewicht|konzern|riese|haus|institut|dienstleister|branche|sektor|wert)\w*",
        "financial services",
    ),
    (r"(?<!n)bank\w*", "financial services"),
)

# Business lines inside the broad financials pool. A vague "Finanz…" word is absent
# on purpose: it must not chart-rank insurers, exchanges and payment networks together.
_FINANCE_LINES = (
    ("insurance", re.compile(r"versicherung\w*|versicherer|\binsurance\b", re.I)),
    (
        "exchanges",
        re.compile(
            r"indexgesch[äa]ft|handelsplatz|b[öo]rsenbetreiber|b[öo]rsenplatz|b[öo]rsenkonzern",
            re.I,
        ),
    ),
    (
        "payments",
        re.compile(r"finanztechnologie|fintech|zahlungs\w*|\bpayments?\b", re.I),
    ),
    (
        "banks",
        re.compile(r"(?<!n)bank\w*|kapitalbasis|kernkapital|\bcet\s*1\b", re.I),
    ),
)


def finance_business_lines(text: str) -> tuple[str, ...]:
    """Concrete finance businesses named by the teaser, in pattern order."""
    clean = stock_text(text)
    return tuple(label for label, pattern in _FINANCE_LINES if pattern.search(clean))


DOMINANCE = (
    r"unverzichtbar|kaum\s+(?:noch\s+)?eine\s+wahl|keine\s+alternative|alternativlos|monopol\w*|"
    r"herrscher|marktbeherrsch\w*|dominier\w*|branchenführer|marktführer|schlüsselrolle|"
    r"nadelöhr|einzigartig\w*"
)


def build_queries(text, named, fallback):
    clean = stock_text(text)
    sector = "company"
    for pattern, label in SECTORS:
        if re.search(pattern, clean, re.I):
            sector = label
            break
    queries = []
    if teaser_wants_hidden_chip_bottleneck(clean):
        queries.extend(HIDDEN_CHIP_QUERIES[:2])
    # HT-202: capital-base language is a bank story even when the word „Bank“ is absent.
    if sector == "banks":
        queries += [
            "bank CET1 ratio record profit dividend buyback resumption investor relations",
            "bank common equity tier 1 strengthened consecutive record earnings",
            "bank capital base distributions resumed earnings release",
        ]
    contexts = []
    for pattern, english in (
        (r"rechenzentr\w*|data\s*cent(?:er|re)", "AI data centers"),
        (r"robot\w*", "robotics"),
        (r"kühl\w*|cooling", "cooling"),
        (r"förder\w*|oilfield", "oilfield services"),
        (r"cloud", "cloud software"),
    ):
        if re.search(pattern, clean, re.I):
            contexts.append(english)
    if re.search(r"zukäuf\w*|übernah\w*|acqui\w*|merger", clean, re.I):
        event = (
            "acquisition rumor"
            if re.search(r"übernahmespekulat\w*|übernahmefantasie|rumou?r|gerücht\w*", clean, re.I)
            else "acquisitions"
        )
        queries.append(" ".join([sector, event] + contexts[:3]) + " investor relations")
    for pattern, event in (
        (r"partnerschaft\w*|kooperation\w*|partnership", "strategic partnership"),
        (r"großauftr\w*|grossauftr\w*|major contract", "major contract"),
        (r"prognos\w*[^.!?]{0,45}angehoben|prognoseanhebung|guidance raise", "raised guidance"),
        (r"zulassung\w*|regulatory approval", "regulatory approval"),
        (r"aktienrückk\w*|share buyback", "share buyback"),
    ):
        if re.search(pattern, clean, re.I):
            queries.append(" ".join([sector, event] + contexts[:2]) + " investor relations")
    if re.search(DOMINANCE, clean, re.I):
        queries.append(
            sector + " dominant supplier customers have no alternative market share monopoly"
        )
        queries.append(sector + " industry indispensable supplier sole source near monopoly")
        if sector == "semiconductor":
            # The dominant firm may sit in any layer of the chip value chain, not only equipment.
            queries += [
                "semiconductor equipment sole supplier market share earnings growth",
                "chip design software duopoly market share customers no alternative",
                "semiconductor IP architecture licensing dominant provider market share",
                "semiconductor foundry materials dominant supplier market share earnings growth",
            ]
    # HT-016 lesson: "Stromhunger / Rechenzentren" fits utilities AND midstream gas.
    # Generic live search collapses to utilities; force value-chain counterqueries so
    # pipeline / natural-gas suppliers can enter the universe without naming a winner.
    if sector == "power infrastructure" and any(ctx in contexts for ctx in ("AI data centers",)):
        queries += [
            "US electric utility data center power purchase agreement earnings IR",
            "utility hyperscale offtake contract capital expenditure plan billion",
            "electric utility long-term data center electricity contract 8-K",
            "natural gas midstream pipeline data center power demand earnings",
            "gas transmission pipeline company long-term contracts power generation AI",
            "midstream energy infrastructure supplier electricity demand data centers",
        ]
    if re.search(r"abnahmevertr\w*|offtake|power purchase|\bPPA\b", clean, re.I):
        queries.append(sector + " power purchase agreement offtake long-term contract earnings")
    if re.search(
        r"investitionsoffensive|capex|capital expenditure|milliarden\w*\s+invest", clean, re.I
    ):
        queries.append(sector + " multi-billion capital investment plan investor relations")
    if re.search(r"wiederkehrend\w*|recurring revenue|\bARR\b", clean, re.I):
        queries.append(sector + ' "recurring revenue" quarterly results')
    if len(contexts) >= 2:
        queries.append(" ".join([sector] + contexts[:3]) + " company annual report")
    metrics = []
    for pattern, english in (
        (r"bruttomarge|gross margin", "gross margin"),
        (r"frei\w*\s*cash\s*flow|free cash flow|\bFCF\b", "free cash flow"),
        (r"operativ\w*\s*cash\s*flow|operating cash flow", "operating cash flow"),
        (r"gewinn je aktie|earnings per share|\bEPS\b", "earnings per share"),
        (r"gewinn|earnings", "earnings"),
        (r"umsatz|revenue", "revenue"),
    ):
        if re.search(pattern, clean, re.I):
            metrics.append('"' + english + '"')
    if re.search(r"cash\s*flow", clean, re.I) and not any("cash flow" in m for m in metrics):
        metrics.append('"cash flow"')
    if metrics:
        query = " ".join([sector] + metrics[:3]) + " quarterly results"
        if re.search(r"analyst\w*|expectations|consensus", clean, re.I):
            query += " analyst expectations"
        queries.append(query)
    elif re.search(r"analyst\w*|rating revision", clean, re.I):
        queries.append(sector + " analyst rating revision investor relations")
    if re.search(r"200[- ]?(?:tage|day)|GD\s*200", clean, re.I):
        queries.append(sector + " stock 200 day moving average support")
    # HT-204 lesson: US defense primes look alike until multi-segment / aftermarket /
    # backlog / guidance-raise cues are searched explicitly.
    if sector == "defense" and re.search(
        r"US[\s-]*Rüstung|amerikanische[rn]?\s+Rüstung|unter\s+einem\s+Dach|"
        r"Wartungsvertr|Auftragsbestand|Prognose\w*\s+angehoben",
        clean,
        re.I,
    ):
        queries += [
            "US aerospace defense conglomerate Raytheon Collins Pratt Whitney segments IR",
            "defense aftermarket maintenance sustainment contracts backlog guidance raise",
            "aerospace defense multi-segment commercial engines military technology earnings",
            "US defense prime peers Lockheed Northrop General Dynamics backlog comparison",
        ]
    safe_named = [name for name in named if name in clean]
    if safe_named:
        queries.append(" ".join('"' + n + '"' for n in safe_named[:3]) + " acquisition investment")
    queries += fallback
    queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
    if teaser_wants_background_chip_profit(clean):
        queries = [q for q in BACKGROUND_CHIP_QUERIES if q not in queries] + queries
    # A raw German headline is a poor web query; keep it only when nothing better exists.
    if clean and len(queries) < 2:
        queries.append(clean[:250] + " company investor relations")
    return queries[:10]


_LATE_QUERY = re.compile(
    r"200[- ]?day|moving average|competitors peer|denied cancelled|peer group",
    re.I,
)
_PRIMARY_QUERY = re.compile(
    r"investor relations|8-K|10-Q|6-K|annual report|earnings|oilfield|"
    r"data center|recurring revenue|backlog|guidance|aftermarket",
    re.I,
)


def prioritize_queries(queries):
    """Sector and filing queries before chart and peer queries.

    Relative order inside each bucket stays as built. A 200-day line or a
    peer-group search no longer consumes the clock ahead of the teaser's sector.
    """
    primary, middle, late = [], [], []
    for query in queries or []:
        text = str(query or "").strip()
        if not text:
            continue
        if _LATE_QUERY.search(text):
            late.append(text)
        elif _PRIMARY_QUERY.search(text):
            primary.append(text)
        else:
            middle.append(text)
    return list(dict.fromkeys([*primary, *middle, *late]))
