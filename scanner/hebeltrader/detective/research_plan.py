"""General research queries from teaser words only; no historical solution imports."""

import re


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
    (r"handels\w*|einzelhandel\w*|retail\w*", "retail"),
    (r"bank\w*|finanz\w*", "financial services"),
)
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
    queries = []
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
    safe_named = [name for name in named if name in clean]
    if safe_named:
        queries.append(" ".join('"' + n + '"' for n in safe_named[:3]) + " acquisition investment")
    queries += fallback
    queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
    # A raw German headline is a poor web query; keep it only when nothing better exists.
    if clean and len(queries) < 2:
        queries.append(clean[:250] + " company investor relations")
    return queries[:10]
