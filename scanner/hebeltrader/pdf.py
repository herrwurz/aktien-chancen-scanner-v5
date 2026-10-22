from io import BytesIO

import pdfplumber


def read_pdf(data: bytes, max_pages=100) -> list[dict]:
    if len(data) > 50 * 1024 * 1024:
        raise ValueError("PDF exceeds 50 MiB limit")
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            if len(pdf.pages) > max_pages:
                raise ValueError("PDF exceeds page limit")
            pages = []
            page_words = [page.extract_words() for page in pdf.pages]
            sidebar_starts = [
                w["x0"] - 8
                for page, words in zip(pdf.pages, page_words, strict=True)
                for w in words
                if w["text"].upper().rstrip(":") in ("WKN", "ISIN")
                and page.width * 0.55 < w["x0"] < page.width * 0.85
            ]
            sidebar = sorted(sidebar_starts)[len(sidebar_starts) // 2] if sidebar_starts else None
            for number, (page, words) in enumerate(zip(pdf.pages, page_words, strict=True), 1):
                tables = [dict(bbox=list(t.bbox), cells=t.extract()) for t in page.find_tables()]
                anchors = sorted({round(w["x0"]) for w in words if w["text"] in ("WKN", "ISIN")})
                starts = []
                for x in anchors:
                    if not starts or x - starts[-1] > page.width * 0.25:
                        starts.append(x)
                bounds = [0 if x < page.width * 0.3 else max(0, x - 8) for x in starts]
                # Keep both columns, including prose-only pages. A known document
                # gutter prevents newsletter text from interleaving with CRV prose.
                if sidebar is not None and not bounds:
                    bounds = [sidebar]
                bounds = sorted(set([0, *bounds]))
                regions = []
                for i, x in enumerate(bounds):
                    right = bounds[i + 1] if i + 1 < len(bounds) else page.width
                    selected = [w for w in words if x <= w["x0"] < right]
                    rows = []
                    for word in sorted(selected, key=lambda w: (round(w["top"] / 3), w["x0"])):
                        if rows and abs(word["top"] - rows[-1][0]["top"]) <= 3:
                            rows[-1].append(word)
                        else:
                            rows.append([word])
                    lines = []
                    for row in rows:
                        row.sort(key=lambda w: w["x0"])
                        lines.append(
                            dict(
                                text=" ".join(w["text"] for w in row),
                                page=number,
                                bbox=[
                                    min(w["x0"] for w in row),
                                    min(w["top"] for w in row),
                                    max(w["x1"] for w in row),
                                    max(w["bottom"] for w in row),
                                ],
                            )
                        )
                    regions.append(lines)
                pages.append(
                    dict(
                        number=number,
                        text=page.extract_text() or "",
                        tables=tables,
                        regions=regions,
                        width=page.width,
                        height=page.height,
                    )
                )
            return pages
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("PDF exceeds"):
            raise
        raise ValueError("PDF could not be read") from exc
