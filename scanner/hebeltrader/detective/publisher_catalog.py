"""Read public publisher catalog/product markup; never follow paid PDF links."""

import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

CATALOG_URL = "https://www.boersenmedien.de/hebeltrader"
_HOSTS = {"www.boersenmedien.de", "boersenmedien.de"}
_PRODUCT = re.compile(r"/produkt/hebeltrader/hebeltrader-(\d{1,3})(\d{2})-\d+\.html$")
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or []), parent
        self.children = []

    def matches_class(self, name):
        return name in self.attrs.get("class", "").split()

    def hidden(self):
        return (
            "hidden" in self.attrs
            or self.attrs.get("aria-hidden", "").lower() == "true"
            or bool(
                re.search(
                    r"display\s*:\s*none|visibility\s*:\s*hidden", self.attrs.get("style", ""), re.I
                )
            )
        )

    def find(self, predicate):
        if self.hidden():
            return []
        result = [self] if predicate(self) else []
        for child in self.children:
            if isinstance(child, _Node):
                result.extend(child.find(predicate))
        return result

    def text(self):
        if self.hidden() or self.tag in {"script", "style", "noscript", "form", "button"}:
            return ""
        return " ".join(
            child.text() if isinstance(child, _Node) else child for child in self.children
        )


class _Markup(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]
        self.feed(raw)

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _clean(text):
    return " ".join(text.split())


def _product_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not _PRODUCT.fullmatch(parsed.path)
    ):
        return None
    return urlunsplit(("https", "www.boersenmedien.de", parsed.path, "", ""))


def catalog_links(raw, url, *, limit=3):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _HOSTS
        or parsed.path.rstrip("/") != "/hebeltrader"
    ):
        raise ValueError("unsupported public publisher catalog")
    links = set()
    for node in _Markup(raw).root.find(lambda n: n.tag == "a"):
        link = _product_url(urljoin(url, node.attrs.get("href", "")))
        if link:
            links.add(link)
    if not links:
        raise ValueError("catalog layout has no public issue links")

    def key(link):
        match = _PRODUCT.fullmatch(urlsplit(link).path)
        return int(match[2]), int(match[1])

    return sorted(links, key=key, reverse=True)[: max(1, min(10, limit))]


def product_teaser(raw, url):
    canonical_url = _product_url(url)
    if canonical_url is None:
        raise ValueError("unsupported public product URL")
    root = _Markup(raw).root
    titles = root.find(
        lambda n: n.tag == "h1" and re.fullmatch(r"HEBELTRADER\s+\d{1,3}/\d{2}", _clean(n.text()))
    )
    descriptions = root.find(lambda n: n.matches_class("single-purchase-description"))
    if len(titles) != 1 or len(descriptions) != 1:
        raise ValueError("ambiguous or missing public teaser layout")
    title, description = titles[0], descriptions[0]
    issue = re.search(r"(\d{1,3})/(\d{2})", title.text())
    path_issue = _PRODUCT.fullmatch(urlsplit(canonical_url).path)
    if (issue[1], issue[2]) != (path_issue[1], path_issue[2]):
        raise ValueError("product URL and issue heading disagree")
    headings = description.find(lambda n: n.tag == "h2")
    if len(headings) != 1:
        raise ValueError("missing or ambiguous teaser headline")
    headline = _clean(headings[0].text())
    visible = _clean(description.text())
    text = visible.partition(headline)[2].strip()
    if not text or len(text) > 20000:
        raise ValueError("empty or oversized public teaser")
    times = title.parent.find(lambda n: n.tag == "time")
    publication_date, published_at = None, None
    if len(times) == 1:
        value = times[0].attrs.get("datetime", "")
        try:
            if len(value) == 10:
                publication_date = date.fromisoformat(value).isoformat()
            else:
                moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if moment.utcoffset() is not None:
                    published_at = moment.isoformat()
                    publication_date = moment.date().isoformat()
        except ValueError:
            pass
    author = ""
    for info in description.parent.find(lambda n: n.matches_class("product-info")):
        if re.match(r"Autor\s*:", _clean(info.text())):
            strong = info.find(lambda n: n.tag == "strong")
            if len(strong) == 1:
                author = _clean(strong[0].text())
    return {
        "url": canonical_url,
        "title": headline,
        "text": text,
        "issue": f"{issue[1]}/{issue[2]}",
        "author": author,
        "publication_date": publication_date,
        "published_at": published_at,
        "publication_precision": "timestamp"
        if published_at
        else "date_only"
        if publication_date
        else "unknown",
        "publisher": "Börsenmedien / DER AKTIONÄR",
        "source_kind": "news",
        "is_public_teaser": True,
        "extraction_method": "public_hebeltrader_product_markup",
    }
