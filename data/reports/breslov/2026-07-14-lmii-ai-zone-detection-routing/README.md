# LM II AI zone-detection routing

`textual_reasoning` routes to `openai_gpt-5.4-nano`; `ocr_layout_zone_detection` routes to `openai_gpt_4o_mini_2024_07_18`, always via LiteLLM. The zone spike is read-only and returns candidate JSON only; it cannot create corpus nodes, authority, or relations.
