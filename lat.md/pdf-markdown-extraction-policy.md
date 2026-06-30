# TebaAI — PDF Markdown Extraction Policy

Estado: accepted.
Fecha: 2026-06-30.

## Decisión

PyMuPDF4LLM es el extractor canónico para PDFs en TebaAI.

El formato canónico persistido en `library_document_texts.content` es Markdown.

## Flujo

```
PDF original
   ↓
PyMuPDF4LLM
   ↓
Markdown
   ↓
library_document_texts.content
   ↓
chunking (generic o structure-aware)
```

## Reglas

- El extractor por defecto para `.pdf` es `pymupdf4llm`.
- El formato por defecto es `markdown`.
- No usar texto plano como fuente principal de ingesta.
- Plain text puede usarse para métricas/preflight/auditoría.
- El chunking posterior opera sobre Markdown.
- No cambiar extractor sin ADR explícito.

## Metadata obligatoria

Cada documento PDF ingestado debe incluir:

```json
{
  "text_extraction": {
    "engine": "pymupdf4llm",
    "format": "markdown",
    "ocr_required": false,
    "source": "local_pdf"
  }
}
```

## Implementación

El extractor está definido en `modules/library/extractors.py`:

```python
".pdf": (TextFormat.MARKDOWN, ExtractionMethod.PYMUPDF4LLM)
```

No hay otra implementación autorizada para PDFs.
