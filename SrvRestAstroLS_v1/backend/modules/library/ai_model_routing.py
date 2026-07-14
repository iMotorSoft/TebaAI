"""Explicit, auditable model routing for bounded library AI tasks."""
from __future__ import annotations
from typing import Literal

TaskType = Literal['textual_reasoning', 'ocr_layout_zone_detection', 'embeddings']
TEXTUAL_REASONING_MODEL = 'openai_gpt-5.4-nano'
OCR_LAYOUT_ZONE_MODEL = 'openai_gpt_4o_mini_2024_07_18'
EMBEDDINGS_MODEL = 'openai_text_embedding_3_small'
ROUTES: dict[TaskType, str] = {
    'textual_reasoning': TEXTUAL_REASONING_MODEL,
    'ocr_layout_zone_detection': OCR_LAYOUT_ZONE_MODEL,
    'embeddings': EMBEDDINGS_MODEL,
}
def model_for_task(task_type: TaskType) -> str:
    """Return only the approved LiteLLM alias for a bounded task."""
    return ROUTES[task_type]
