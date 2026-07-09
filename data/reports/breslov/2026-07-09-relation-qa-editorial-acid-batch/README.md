# Relation QA Editorial Acid Batch — 2026-07-09

Evaluación editorial de `POST /library/relation-qa` para uso investigativo en el corpus Breslov.

## Contenido

```
├── README.md                          ← Este archivo
├── batch_questions.json               ← 10 preguntas con metadatos
├── raw/                               ← Respuestas JSON crudas
│   ├── 01-sangre-habla.json
│   ├── 02-tristeza.json
│   └── ...
├── rendered/                          ← Versión Markdown legible
│   ├── 01-sangre-habla.md
│   ├── 02-tristeza.md
│   └── ...
├── editorial_scores.md                ← Puntajes editoriales 0-3 por criterio
├── findings.md                        ← Hallazgos clasificados
└── recommendations.md                 ← Recomendaciones P0/P1/P2
```

## Resultado global

- **Promedio editorial**: 17.3/24 (PASS usable)
- **PASS fuerte**: 1
- **PASS usable**: 7
- **WARN**: 2
- **FAIL**: 0

## Problema principal (P0)

AI synthesis (`openai_gpt-5.4-nano` vía LiteLLM) falla 30-50% de las consultas con `ai_response_parse_failed`. Cuando falla, la respuesta editorial es genérica (solo lista fuentes). Esto impacta directamente la utilidad investigativa.

## Archivos canónicos

- Harness: `SrvRestAstroLS_v1/backend/scripts/relation_qa_editorial_acid_batch.py`
- Preguntas: `data/reports/breslov/2026-07-09-relation-qa-editorial-acid-batch/batch_questions.json`

## Servicios verificados

- PostgreSQL: OK (Docker, pgvector/pgvector:pg18-trixie)
- Milvus: OK (Docker, milvusdb/milvus:v2.6.14)
- LiteLLM: OK (http://127.0.0.1:4000)
- Backend: OK (127.0.0.1:7008)
- Astro: no levantado (no necesario para este batch)
