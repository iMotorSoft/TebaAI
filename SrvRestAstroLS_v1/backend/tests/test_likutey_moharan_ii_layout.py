from modules.library.likutey_moharan_ii_layout import classify_page

def test_hebrew_main_and_numbered_notes_are_separate():
    pieces = classify_page([(10, 180, 400, 420, "וְ אֵ לֶּ ה " * 30), (10, 500, 400, 600, "2. Nota explicativa")], 12)
    assert [piece.kind for piece in pieces] == ["hebrew_main_text", "numbered_footnote"]

def test_spanish_translation_and_header_are_separate():
    pieces = classify_page([(10, 130, 400, 140, "LIKUTEY MOHARÁN #7:1"), (10, 230, 400, 420, "La plegaria es sobrenatural."), (10, 500, 400, 600, "1. Nota")], 13)
    assert [piece.kind for piece in pieces] == ["page_header", "spanish_translation", "numbered_footnote"]

def test_ambiguous_body_falls_back_to_unknown():
    pieces = classify_page([(10, 230, 400, 420, "abc אבג")], 3)
    assert pieces[0].kind == "unknown"

def test_unknown_piece_is_not_a_footnote():
    pieces = classify_page([(10, 500, 400, 600, "sin marcador")], 13)
    assert pieces[0].kind == "unknown"
