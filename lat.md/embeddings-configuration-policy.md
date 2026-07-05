# TebaAI — Embeddings Configuration Policy

Estado: accepted.
Fecha: 2026-06-30.

## Contexto

TebaAI usa embeddings a través de LiteLLM como gateway. La clave upstream de OpenAI (`OpenAI_Key_JAI_query`) se resuelve exclusivamente dentro de la configuración de LiteLLM (`config.yaml`). TebaAI no gestiona claves directas de OpenAI.

## Arquitectura

```
OpenAI_Key_JAI_query
       ↓
LiteLLM config.yaml
       ↓
API compatible OpenAI en http://127.0.0.1:4000
       ↓
TebaAI llama a LiteLLM con su master key
       ↓
Milvus recibe embeddings
```

## Configuración

| Variable | Propósito | Default |
|----------|-----------|---------|
| `TEBAAI_LITELLM_BASE_URL` | URL del proxy LiteLLM | `http://127.0.0.1:4000` |
| `LITELLM_MASTER_KEY` | Variable primaria global (convención entre proyectos) | — |
| `TEBAAI_LITELLM_API_KEY` | Fallback específico TebaAI (override local) | — |
| `TEBAAI_EMBEDDINGS_MODEL_ALIAS` | Alias interno del modelo | `openai_text_embedding_3_small` |
| `TEBAAI_EMBEDDINGS_DIMENSION` | Dimensión del vector | 1536 |
| `TEBAAI_EMBEDDINGS_BATCH_SIZE` | Textos por batch | 16 |

### Precedencia de resolución de API key

```
1. LITELLM_MASTER_KEY — fuente primaria global (convención iMotorSoft).
2. TEBAAI_LITELLM_API_KEY — fallback específico TebaAI.
```

La resolución se centraliza en `core/config.py` (validador `_validate_litellm`).
`globalVar.py` exporta `LITELLM_API_KEY` como string normalizado.
El usuario solo necesita `LITELLM_MASTER_KEY` en su entorno (`.bashrc`).
No requiere anteponer `TEBAAI_LITELLM_API_KEY="${LITELLM_MASTER_KEY}"` en comandos.

`TEBAAI_EMBEDDINGS_API_KEY` no es requisito canónico. La clave upstream de OpenAI se resuelve dentro de LiteLLM.

## Cuándo requiere embeddings

Requiere embeddings:
- Indexar chunks en Milvus.
- Crear vectores nuevos.
- Reindexar colección vectorial.
- Búsqueda vectorial con embedding de query.
- Búsqueda híbrida con rama vectorial.

No requiere embeddings:
- FTS PostgreSQL.
- Page mapping.
- Metadata enrichment.
- Conteos.
- Validaciones Git.
- Documentación.

## Seguridad

- `LITELLM_API_KEY` se expone en `globalVar.py` como string seguro.
- No se imprime la clave en logs, errores ni respuestas HTTP.
- No se exponen claves al frontend.
- `OpenAI_Key_JAI_query` no aparece en código de TebaAI.
