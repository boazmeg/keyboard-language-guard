from mapper import convert_layout, direction


def test_en_to_he_roundtrip_phrases():
    assert convert_layout("akuo nv eurv") == "שלום מה קורה"
    assert convert_layout("tbh rumv kf,uc ntus") == "אני רוצה לכתוב מאוד"


def test_he_to_en_reverses_en_to_he():
    hebrew = "שלום מה קורה"
    english_keys = convert_layout(hebrew)
    assert english_keys == "akuo nv eurv"


def test_whitespace_is_preserved():
    assert convert_layout("a b\tc\nd") == "ש נ\tב\nג"


def test_direction_detects_mostly_latin():
    assert direction("akuo nv eurv") == "en_to_he"


def test_direction_detects_mostly_hebrew():
    assert direction("שלום מה קורה") == "he_to_en"


def test_direction_none_for_short_or_mixed():
    assert direction("ab") is None


def test_unknown_characters_pass_through():
    # Digits are not on the layout map, so they pass through unchanged.
    assert convert_layout("abc123", "en_to_he") == "שנב123"
