from modules.library.ai_model_routing import model_for_task

def test_zone_detection_uses_specialized_litellm_alias():
    assert model_for_task('ocr_layout_zone_detection') == 'openai_gpt_4o_mini_2024_07_18'
    assert model_for_task('textual_reasoning') == 'openai_gpt-5.4-nano'
