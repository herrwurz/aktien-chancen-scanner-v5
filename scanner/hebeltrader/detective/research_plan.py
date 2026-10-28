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
        queries.append(" ".join([sector, "acquisitions"] + contexts[:3]) + " investor relations")
    if len(contexts) >= 2:
        queries.append(" ".join([sector] + contexts[:3]) + " company annual report")
    metrics = []
    for pattern, english in (
        (r"bruttomarge|gross margin", "gross margin"),
        (r"cash\s*flow", "free cash flow"),
        (r"gewinn|earnings", "earnings"),
        (r"umsatz|revenue", "revenue"),
    ):
        if re.search(pattern, clean, re.I):
            metrics.append('"' + english + '"')
    if metrics:
        queries.append(" ".join([sector] + metrics[:3]) + " quarterly results")
    safe_named = [name for name in named if name in clean]
    if safe_named:
        queries.append(" ".join('"' + n + '"' for n in safe_named[:3]) + " acquisition investment")
    if clean:
        queries.append(clean[:250] + " company investor relations")
    queries += fallback
    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:8]
