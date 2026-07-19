from modules.library.likutey_moharan_ii_layout import _readable_line, classify_page, readable_page_text

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

def test_rebuilds_hebrew_from_geometry_without_manual_reversal():
    line = {"spans": [{"chars": [
        {"c": "א", "bbox": (30, 0, 38, 10)}, {"c": "ָ", "bbox": (30, 0, 38, 10)},
        {"c": "מ", "bbox": (22, 0, 30, 10)}, {"c": "ַ", "bbox": (22, 0, 30, 10)},
        {"c": "ר", "bbox": (14, 0, 22, 10)}, {"c": " ", "bbox": (10, 0, 14, 10)},
        {"c": "ל", "bbox": (2, 0, 8, 10)}, {"c": "ִ", "bbox": (2, 0, 8, 10)},
    ]}]}
    assert _readable_line(line) == "אָמַר לִ"

def test_real_projection_merges_the_section_heading_and_omits_page_number():
    text = readable_page_text(28)
    if text is not None:
        assert text.startswith("ה וְזֶה פֵּרוּשׁ:")
        assert not text.startswith("18")
