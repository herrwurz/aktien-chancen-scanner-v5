from scanner.hebeltrader.detective.structure_screen import load_universe


def test_every_universe_asset_has_a_ticker():
    load_universe.cache_clear()
    assets = load_universe()
    assert len(assets) >= 100
    missing = [asset["name"] for asset in assets if not asset.get("ticker")]
    assert missing == []


def test_exchange_suffixes_present_for_non_us_names():
    load_universe.cache_clear()
    by_name = {asset["name"]: asset["ticker"] for asset in load_universe()}
    assert by_name["SAP"].endswith(".XETRA")
    assert by_name["Tokyo Electron"].endswith(".TSE")
    assert by_name["Samsung Electronics"].endswith(".KO")
    assert "." not in by_name["JPMorgan Chase"]
