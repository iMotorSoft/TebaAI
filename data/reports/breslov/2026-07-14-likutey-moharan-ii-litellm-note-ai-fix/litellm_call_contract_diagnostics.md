# LiteLLM call contract diagnostics

Causa raíz: el adjudicador v1 enviaba `LITELLM_DEFAULT_MODEL_ALIAS`, que estaba vacío; LiteLLM devolvía HTTPStatusError. Relation QA usa `RESEARCH_CONVERSATION_MODEL=openai_gpt-5.4-nano`. v2 replica su endpoint `/v1/chat/completions`, autorización Bearer, `Content-Type`, timeout configurado, `temperature=0`, `max_tokens=700` y `response_format=json_object`, con parseo y un retry de JSON.
