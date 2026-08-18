from detector import detect_wrong_layout


def test_detects_hebrew_typed_in_english():
    result = detect_wrong_layout("akuo nv eurv tbh rumv kf,uc")
    assert result is not None
    assert result.converted == "שלום מה קורה אני רוצה לכתוב"
    assert result.source_lang == "en"
    assert result.target_lang == "he"
    assert 0.0 < result.confidence <= 0.99


def test_ignores_normal_english():
    assert detect_wrong_layout("hello this is a perfectly normal sentence") is None


def test_ignores_normal_hebrew():
    assert detect_wrong_layout("שלום זה משפט עברי רגיל לחלוטין") is None


def test_ignores_text_below_min_chars():
    assert detect_wrong_layout("akuo") is None


def test_requires_at_least_two_words():
    # A single long token should not trigger even if it converts.
    assert detect_wrong_layout("akuoeurv", min_words=2) is None


def test_ignores_random_gibberish():
    # Random keys that are not a hidden Hebrew phrase should stay quiet.
    assert detect_wrong_layout("xkcd qwpz vbnm asdf") is None
