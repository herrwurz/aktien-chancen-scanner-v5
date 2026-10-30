"""Deterministic shortlist from a sector/layer/market-structure universe (no web, no AI).

Teaser words select the sector; dominance wording ("kaum eine Wahl", "unverzichtbar")
favours concentrated market structures. The result is diversified across value-chain
layers so that no single well-known layer can crowd out the others.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from .research_plan import DOMINANCE, SECTORS, stock_text

UNIVERSE = Path(__file__).resolve().parent / "global_universe.json"
STRUCTURE_WEIGHT = {"monopoly": 3, "duopoly": 3, "oligopoly": 2, "fragmented": 0}
CHOICE = r"kaum\s+(?:noch\s+)?eine\s+wahl|keine\s+alternative|alternativlos|unverzichtbar"


@lru_cache(maxsize=1)
def load_universe(path=UNIVERSE):
    return json.loads(Path(path).read_text(encoding="utf-8"))["assets"]


def sectors_in(text):
    clean = stock_text(text)
    return [label for pattern, label in SECTORS if re.search(pattern, clean, re.I)]


def screen(text, *, limit=8, per_layer=2, universe=None):
    sectors = sectors_in(text)
    if not sectors:
        return []
    clean = stock_text(text)
    dominant = bool(re.search(DOMINANCE, clean, re.I))
    no_choice = bool(re.search(CHOICE, clean, re.I))
    ranked = []
    seen = set()
    for asset in universe if universe is not None else load_universe():
        if asset["sector"] not in sectors or asset["name"] in seen:
            continue
        seen.add(asset["name"])
        weight = STRUCTURE_WEIGHT.get(asset["structure"], 0)
        score = weight * (2 if no_choice else 1 if dominant else 0)
        ranked.append((score, asset))
    ranked.sort(key=lambda item: -item[0])
    layers = {}
    for _, asset in ranked:
        layers.setdefault(asset["layer"], []).append(asset)
    top = {layer: max(s for s, a in ranked if a["layer"] == layer) for layer in layers}
    order = sorted(layers, key=lambda layer: -top[layer])
    picked = []

    def take(asset):
        if len(picked) < limit and asset not in picked:
            picked.append(asset)

    # Concentrated layers (duopoly/monopoly cues) are listed completely so that every
    # player of the layer is a candidate; the remaining layers are sampled round-robin.
    for layer in order:
        if top[layer] > 0 and layers[layer][0]["structure"] in ("monopoly", "duopoly"):
            for asset in layers[layer][:per_layer]:
                take(asset)
    for depth in range(per_layer):
        for layer in order:
            if depth < len(layers[layer]):
                take(layers[layer][depth])
    return picked


def screen_queries(text, **options):
    return [
        f'"{asset["name"]}" market position customers alternatives competitors'
        for asset in screen(text, **options)
    ]
