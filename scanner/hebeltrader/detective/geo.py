"""Country/region matching for hypothesis constraints."""

REGION_MEMBERS = {
    "EU": {
        "AT",
        "BE",
        "CH",
        "DE",
        "DK",
        "ES",
        "FI",
        "FR",
        "IE",
        "IT",
        "LU",
        "NL",
        "PL",
        "SE",
    },
    "DACH": {"AT", "CH", "DE"},
    "Europe": {
        "AT",
        "BE",
        "CH",
        "DE",
        "DK",
        "ES",
        "FI",
        "FR",
        "GB",
        "IE",
        "IT",
        "LU",
        "NL",
        "NO",
        "PL",
        "SE",
    },
}


def country_matches(clue_value: str | None, asset_country: str | None) -> bool:
    if not clue_value or not asset_country:
        return False
    if clue_value == asset_country:
        return True
    members = REGION_MEMBERS.get(clue_value)
    return bool(members and asset_country in members)
