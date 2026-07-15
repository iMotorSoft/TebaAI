# Breslov Conversational Investigative QA API V1

Endpoint: `POST /library/investigative-qa/v1`. La recuperación es SQL literal mediante adaptadores permitidos; PostgreSQL y las quotes recuperadas son la autoridad. LiteLLM con `openai_gpt-5.4-nano` se intenta para interpretación y render cerrado; ante indisponibilidad se usa fallback determinístico con warning. La CLI consume HTTP, no módulos internos.
