from scanner.hebeltrader.detective.investigation import _interleave
from scanner.hebeltrader.detective.structure_screen import load_universe, screen, screen_queries

DOMINANT = (
    "Der heimliche Herrscher über die globale Chipindustrie: unverzichtbar, "
    "Kunden haben kaum noch eine Wahl. Optionsschein Call WKN ABC123"
)


def test_dominance_teaser_shortlist_covers_concentrated_layers():
    names = [a["name"] for a in screen(DOMINANT)]
    assert {"ASML Holding", "Synopsys", "Cadence Design Systems"} <= set(names)
    assert {a["structure"] for a in screen(DOMINANT)[:4]} <= {"monopoly", "duopoly"}


def test_shortlist_is_diversified_and_sector_bound():
    picked = screen(DOMINANT, limit=8, per_layer=2)
    assert {a["sector"] for a in picked} == {"semiconductor"}
    assert (
        max(sum(a["layer"] == layer for a in picked) for layer in {a["layer"] for a in picked}) <= 2
    )


def test_unknown_sector_yields_no_shortlist():
    assert screen("Ein Unternehmen mit Zukunft") == []
    assert screen_queries("Ein Unternehmen mit Zukunft") == []


def test_universe_has_no_teaser_solutions_metadata_only():
    assert all(
        set(a) <= {"name", "sector", "layer", "structure", "ticker"} for a in load_universe()
    )


def test_interleave_alternates_and_caps():
    merged = _interleave(["p1", "p2"], ["s1", "s2"], ["f1"], cap=10)
    assert merged == ["p1", "s1", "p2", "s2", "f1"]
    assert len(_interleave([f"p{i}" for i in range(9)], [f"s{i}" for i in range(9)], [])) == 10


def test_structure_bonus_only_for_no_choice_wording_and_concentrated_layers():
    from scanner.hebeltrader.detective.structure_screen import structure_bonus

    assert structure_bonus("Synopsys", DOMINANT)["bonus"] == 15
    assert structure_bonus("Nvidia", DOMINANT)["bonus"] == 2
    assert structure_bonus("Synopsys", "Starkes Wachstum bei Chips") is None
    assert structure_bonus("Unbekannt", DOMINANT) is None


def test_hypothesis_name_matches_legal_form_variants():
    from scanner.hebeltrader.detective.investigation import _is_hypothesis

    assert _is_hypothesis("Synopsys Inc.", ["Synopsys"])
    assert not _is_hypothesis("Nvidia", ["Synopsys"])
