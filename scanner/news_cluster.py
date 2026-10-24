"""Deterministic event clustering without multiplying syndicated evidence."""

import re
from datetime import timedelta

from pydantic import BaseModel

from scanner.news import NewsItem


class NewsCluster(BaseModel):
    cluster_id: str
    items: list[NewsItem]
    publication_urls: list[str]
    independent_origin_count: int
    strongest_source_type: str


def _tokens(value):
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _identifier_tokens(item):
    return {(kind, value) for kind, values in item.company_identifiers.items() for value in values}


def _similar(left, right):
    if left.event_type != right.event_type:
        return False
    if abs(left.published_at - right.published_at) > timedelta(hours=36):
        return False
    identifiers = _identifier_tokens(left) & _identifier_tokens(right)
    if not identifiers:
        return False
    left_tokens, right_tokens = _tokens(left.title), _tokens(right.title)
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    return left.origin_id == right.origin_id or overlap >= 0.75


def cluster_news(items):
    groups = []
    for candidate in sorted(items, key=lambda row: (row.published_at, row.source_id)):
        group = next(
            (rows for rows in groups if any(_similar(candidate, row) for row in rows)), None
        )
        if group is None:
            groups.append([candidate])
        else:
            group.append(candidate)
    priority = {"PRIMARY": 3, "SECONDARY": 2, "COMMUNITY": 1}
    result = []
    for rows in groups:
        origins = {row.origin_id for row in rows}
        result.append(
            NewsCluster(
                cluster_id=min(origins),
                items=rows,
                publication_urls=list(dict.fromkeys(row.url for row in rows)),
                independent_origin_count=len(origins),
                strongest_source_type=max(
                    rows, key=lambda row: priority[row.source_type]
                ).source_type,
            )
        )
    return result
