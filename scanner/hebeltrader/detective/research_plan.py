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


def build_queries(text, named, fallback):
    clean = stock_text(text)
    sector = (
        "semiconductor"
        if re.search(r"halbleiter|\bchip\w*|semiconductor", clean, re.I)
        else "company"
    )
    if sector == "company":
        for pattern, label in (
            (r"landmaschinen\w*|traktor\w*|agrartechnik|agricultural", "agricultural machinery"),
            (r"versicherung\w*|versicherer|insurance", "insurance"),
            (r"pharma\w*|biotech\w*", "pharmaceutical"),
            (r"software\w*", "software"),
        ):
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
    if clean:
        queries.append(clean[:250] + " company investor relations")
    queries += fallback
    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:8]
