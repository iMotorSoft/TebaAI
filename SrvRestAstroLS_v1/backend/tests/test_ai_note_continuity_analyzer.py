from modules.library.ai_note_continuity_analyzer import fallback
def test_fallback_is_citable_unlinked():
    result=fallback("timeout")
    assert result.decision == "citable_unlinked_satellite" and result.requires_human_review
