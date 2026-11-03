"""Defense / aerospace fingerprints: multi-segment conglomerate + aftermarket.

HT-204 lesson (RTX vs Lockheed): generic „Rüstungsriese / Auftragsboom / Gewinne“
hits every US prime. The teaser cue „mehrere Weltmarktführer unter einem Dach“ plus
Wartungsverträge / Guidance-Raise / Rekord-Backlog must decide before chart noise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TEASER_DEFENSE = re.compile(
    r"rüstung\w*|verteidigung\w*|defen[sc]e|aerospace|militär\w*|waffen\w*",
    re.I,
)
_TEASER_US_DEFENSE = re.compile(
    r"US[\s-]*Rüstung\w*|US[\s-]*Defense|US[\s-]*Aerospace|"
    r"amerikanische[rn]?\s+Rüstung\w*|amerikanischer?\s+Rüstungs|"
    r"US[\s-]*Rüstungsriese|US[\s-]*Rüstungskonzern",
    re.I,
)
_TEASER_MULTI_SEGMENT = re.compile(
    r"mehrere\s+Weltmarktführer\s+unter\s+einem\s+Dach|"
    r"Weltmarktführer\w*\s+unter\s+einem\s+Dach|"
    r"vereint\s+(?:gleich\s+)?mehrere\s+Weltmarktführer|"
    r"unter\s+einem\s+Dach|"
    r"multi[\s-]*segment|mehrere\s+Geschäftsbereiche",
    re.I,
)
_TEASER_AFTERMARKET = re.compile(
    r"wartungsvertr[äa]g\w*|wartungsgeschäft|aftermarket|"
    r"service(?:geschäft|vertr[äa]g\w*)|instandhaltung",
    re.I,
)
_TEASER_BACKLOG = re.compile(
    r"auftragsbestand\w*|order\s+backlog|backlog|"
    r"rekord(?:auftrag|auftrags)|historischer?\s+Rekord",
    re.I,
)
_TEASER_GUIDANCE = re.compile(
    r"prognos\w*[^.!?]{0,40}angehoben|jahresprognose\w*\s+angehoben|"
    r"prognoseanhebung|guidance\s+raise|raised\s+guidance|"
    r"jahresprognose\s+kräftig",
    re.I,
)

# English IR / 10-Q cues that mark a multi-segment aerospace conglomerate.
_MULTI_SEGMENT_DOC = re.compile(
    r"(?:"
    r"\bRaytheon\b|\bCollins\s+Aerospace\b|\bPratt\s*(?:&|and)\s*Whitney\b|"
    r"United\s+Technologies|"
    r"(?:three|four|multi)[\s-]*(?:business\s+)?segments?|"
    r"reportable\s+segments?|"
    r"commercial\s+engines?\s+and\s+(?:defense|military)|"
    r"aerospace\s+and\s+defense\s+segments?"
    r")",
    re.I,
)
_AFTERMARKET_DOC = re.compile(
    r"(?:"
    r"aftermarket|maintenance(?:\s+contracts?)?|sustainment|"
    r"service\s+(?:revenue|contracts?|agreements?)|"
    r"spare\s+parts|MRO\b|long[\s-]*term\s+service"
    r")",
    re.I,
)
_BACKLOG_DOC = re.compile(
    r"(?:"
    r"(?:record|all[\s-]*time\s+high|histor(?:ic|ical))\s+(?:order\s+)?backlog|"
    r"backlog\s+(?:reached|hit|at)\s+(?:a\s+)?(?:record|all[\s-]*time)|"
    r"total\s+backlog.{0,40}record|"
    r"Rekord[\s-]*Auftragsbestand|Auftragsbestand.{0,30}Rekord"
    r")",
    re.I,
)
_GUIDANCE_DOC = re.compile(
    r"(?:"
    r"raised\s+(?:full[\s-]*year\s+)?(?:guidance|outlook|forecast)|"
    r"(?:increased|lifted|raised)\s+(?:its\s+)?(?:202\d|full[\s-]*year)\s+"
    r"(?:guidance|outlook|forecast)|"
    r"guidance\s+(?:raise|increase|upward\s+revision)|"
    r"Jahresprognose\s+angehoben|Prognose\s+angehoben"
    r")",
    re.I,
)

# Pure-play primes: lose when teaser insists on multi-world-leader conglomerate
# and their docs lack multi-segment evidence.
_PURE_PLAY_PRIMES = re.compile(
    r"\b("
    r"lockheed\s+martin|northrop\s+grumman|general\s+dynamics|"
    r"huntington\s+ingalls|bae\s+systems|leonardo|thales|rheinmetall|"
    r"l3harris|saab\b|hensoldt"
    r")\b",
    re.I,
)
_KNOWN_EU_DEFENSE = re.compile(
    r"\b("
    r"rheinmetall|leonardo|thales|bae\s+systems|saab|hensoldt|"
    r"airbus\s+defence|dassault\s+aviation|knds|renault\s+trucks\s+defense"
    r")\b",
    re.I,
)


def teaser_wants_defense_fingerprint(text: str) -> bool:
    blob = text or ""
    if not _TEASER_DEFENSE.search(blob):
        return False
    return bool(
        _TEASER_MULTI_SEGMENT.search(blob)
        or _TEASER_AFTERMARKET.search(blob)
        or _TEASER_BACKLOG.search(blob)
        or _TEASER_GUIDANCE.search(blob)
        or _TEASER_US_DEFENSE.search(blob)
    )


def teaser_requires_us_defense(text: str) -> bool:
    return bool(_TEASER_US_DEFENSE.search(text or ""))


def teaser_claims_multi_segment_defense(text: str) -> bool:
    return bool(_TEASER_MULTI_SEGMENT.search(text or ""))


@dataclass(frozen=True)
class DefenseFingerprint:
    multi_segment: bool = False
    aftermarket: bool = False
    record_backlog: bool = False
    raised_guidance: bool = False

    @property
    def components(self) -> int:
        return sum(
            [
                self.multi_segment,
                self.aftermarket,
                self.record_backlog,
                self.raised_guidance,
            ]
        )


def extract_defense_fingerprint(text: str) -> DefenseFingerprint:
    blob = text or ""
    return DefenseFingerprint(
        multi_segment=bool(_MULTI_SEGMENT_DOC.search(blob)),
        aftermarket=bool(_AFTERMARKET_DOC.search(blob)),
        record_backlog=bool(_BACKLOG_DOC.search(blob)),
        raised_guidance=bool(_GUIDANCE_DOC.search(blob)),
    )


def defense_fingerprint_score(fingerprint: DefenseFingerprint, *, teaser_text: str = "") -> int:
    if fingerprint.components == 0:
        return 0
    score = 0
    if fingerprint.multi_segment:
        score += 28
    if fingerprint.aftermarket:
        score += 14
    if fingerprint.record_backlog:
        score += 8
    if fingerprint.raised_guidance:
        score += 12
    if fingerprint.multi_segment and fingerprint.aftermarket:
        score += 16
    if fingerprint.components >= 3:
        score += 10
    # Extra weight when the teaser itself demands the conglomerate cue.
    if teaser_claims_multi_segment_defense(teaser_text) and fingerprint.multi_segment:
        score += 8
    return score


def _fingerprint_scan(documents: list[dict]) -> DefenseFingerprint:
    multi = after = backlog = guidance = False
    for doc in documents or []:
        text = str(doc.get("text") or "")
        if doc.get("title"):
            text = str(doc["title"]) + "\n" + text
        found = extract_defense_fingerprint(text)
        multi = multi or found.multi_segment
        after = after or found.aftermarket
        backlog = backlog or found.record_backlog
        guidance = guidance or found.raised_guidance
    return DefenseFingerprint(
        multi_segment=multi,
        aftermarket=after,
        record_backlog=backlog,
        raised_guidance=guidance,
    )


def fingerprint_from_documents(documents: list[dict]) -> DefenseFingerprint:
    from .source_kind import document_is_primary

    docs = list(documents or [])
    primary = [d for d in docs if document_is_primary(d)]
    primary_fp = _fingerprint_scan(primary)
    all_fp = _fingerprint_scan(docs)
    # Prefer primary multi-segment / aftermarket; allow backlog/guidance from any doc.
    return DefenseFingerprint(
        multi_segment=primary_fp.multi_segment or all_fp.multi_segment,
        aftermarket=primary_fp.aftermarket or all_fp.aftermarket,
        record_backlog=all_fp.record_backlog or primary_fp.record_backlog,
        raised_guidance=all_fp.raised_guidance or primary_fp.raised_guidance,
    )


def _looks_pure_play_prime(identity: dict) -> bool:
    return bool(_PURE_PLAY_PRIMES.search(identity.get("name") or ""))


def issuer_looks_non_us_defense(identity: dict) -> bool:
    country = (identity.get("country") or "").strip().upper()
    if country and country not in {
        "US",
        "USA",
        "UNITED STATES",
        "UNITED STATES OF AMERICA",
    }:
        return True
    ticker = identity.get("ticker") or ""
    if re.search(r"\.(PA|MI|XETRA|DE|L|AS|BR|ST|HE|CO|OL|LS|WA|MC)$", ticker, re.I):
        return True
    return bool(_KNOWN_EU_DEFENSE.search(identity.get("name") or ""))


def apply_defense_fingerprints(
    ranked: list[dict], documents_by_asset: dict[str, list[dict]], *, teaser_text: str = ""
) -> dict:
    """Boost multi-segment / aftermarket defense evidence; demote pure-plays when needed."""
    from .source_kind import document_is_primary

    summary = {"status": "applied", "scored": []}
    if not teaser_wants_defense_fingerprint(teaser_text):
        summary["status"] = "skipped_no_defense_cues"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary

    wants_multi = teaser_claims_multi_segment_defense(teaser_text)
    for row in ranked:
        docs = documents_by_asset.get(row.get("asset_id")) or []
        docs = docs if isinstance(docs, list) else []
        primary = [d for d in docs if document_is_primary(d)]
        primary_fp = _fingerprint_scan(primary)
        fingerprint = fingerprint_from_documents(docs)
        bonus = defense_fingerprint_score(fingerprint, teaser_text=teaser_text)
        provenance = "primary" if primary_fp.components >= 1 else "secondary_or_mixed"
        if fingerprint.multi_segment and not primary_fp.multi_segment:
            bonus = max(0, bonus - 10)
            provenance = "secondary_multi_segment"

        identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
        soft_demote = 0
        if (
            wants_multi
            and _looks_pure_play_prime(identity)
            and not fingerprint.multi_segment
            and not row.get("hard_contradictions")
        ):
            # Soft demotion: pure-play primes without conglomerate evidence lose to
            # multi-segment peers when the teaser demands „unter einem Dach“.
            soft_demote = 22
            counters = list(row.get("counterarguments") or [])
            note = (
                "Teaser verlangt mehrere Weltmarktführer unter einem Dach; "
                "Kandidat wirkt wie Pure-Play-Prime ohne Multi-Segment-Beleg."
            )
            if note not in counters:
                counters.append(note)
            row["counterarguments"] = counters

        delta = bonus - soft_demote
        row["defense_fingerprint"] = {
            "multi_segment": fingerprint.multi_segment,
            "aftermarket": fingerprint.aftermarket,
            "record_backlog": fingerprint.record_backlog,
            "raised_guidance": fingerprint.raised_guidance,
            "components": fingerprint.components,
            "bonus": bonus,
            "soft_demote": soft_demote,
            "provenance": provenance,
            "primary_components": primary_fp.components,
        }
        if delta and not row.get("hard_contradictions"):
            row["evidence_score"] = int(row.get("evidence_score") or 0) + delta
        summary["scored"].append(
            {
                "asset_id": row.get("asset_id"),
                "bonus": bonus,
                "soft_demote": soft_demote,
                "components": fingerprint.components,
                "provenance": provenance,
            }
        )

    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -row.get("evidence_score", 0),
            row.get("asset_id") or "",
        )
    )
    return summary
