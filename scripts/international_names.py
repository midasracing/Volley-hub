"""Verified Latin-script display names for 2026/27 men's SV.League teams.

The keys are the exact short labels published by svleague.jp. Do not
transliterate mechanically: sponsors, acronyms and city names are branded.
English names verified against Volleyball World 2026/27 team list.
"""

JAPANESE_TEAM_NAMES = {
    "F鹿児島": "Fragolad Kagoshima",
    "STINGS愛知": "JTEKT Stings Aichi",
    "WD名古屋": "Wolfdogs Nagoya",
    "サントリー": "Suntory Sunbirds Osaka",
    "ヴォレアス": "Voreas Hokkaido",
    "北海道YS": "Hokkaido Yellow Stars",
    "大阪Ｂ": "Osaka Bluteon",
    "広島TH": "Hiroshima Thunders",
    "日鉄堺BZ": "Nippon Steel Sakai Blazers",
    "東レ静岡": "Toray Arrows Shizuoka",
    "東京GB": "Tokyo Great Bears",
    "松本TD": "Shinshu Matsumoto Tridents",
}

def romanize_team(source_name):
    """Fail closed when a new Japanese abbreviation is introduced."""
    try:
        return JAPANESE_TEAM_NAMES[source_name]
    except KeyError as error:
        raise ValueError(f"Unknown SV.League team abbreviation: {source_name!r}") from error
