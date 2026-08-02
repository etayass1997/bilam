import app


def test_hebrew_number():
    assert app._hebrew_number(1) == "א׳"
    assert app._hebrew_number(12) == "י״ב"
    assert app._hebrew_number(15) == "ט״ו"
    assert app._hebrew_number(16) == "ט״ז"
    assert app._hebrew_number(22) == "כ״ב"


def test_source_label_always_has_parasha_and_hebrew_reference():
    meta = {
        "parasha": "פרשת בלק",
        "chapter": 22,
        "verse": 3,
        "commentator_name": "רש״י",
    }
    assert app._format_source_label(meta) == "פרשת בלק, פרק כ״ב, פסוק ג׳ — רש״י"


def test_source_label_normalizes_parasha_prefix():
    meta = {"parasha": "בלק", "chapter": "12", "verse": "1"}
    assert app._format_source_label(meta) == "פרשת בלק, פרק י״ב, פסוק א׳ — טקסט התורה"
