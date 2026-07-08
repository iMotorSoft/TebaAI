# Document Source Quality Policy — TebaAI / Breslov

Estado: approved (internal governance).

Fecha: 2026-07-02.

## 1. Propósito

Definir criterios técnicos y bibliográficos para clasificar, promover y
descartar fuentes documentales dentro de TebaAI. La calidad de la fuente
determina si puede usarse como texto canónico, texto auxiliar, referencia
visual o si debe rechazarse.

## 2. Alcance

Aplica a toda fuente documental ingresada en `breslov_test` o cualquier
colección TebaAI. Cubre PDFs, texto plano, Markdown, decodificaciones
especiales y futuras fuentes nativas digitales.

No cubre:
- BM25 / RRF (son capas de retrieval sobre texto ya calificado).
- Normalización lexical (es auxiliar, no canónica).
- Shoresh/lemas (fuera de alcance hasta ADR separado).
- OCR (fuera de alcance hasta ADR).

## 3. Taxonomía de fuente documental

### 3.1 `source_kind` (clasificación)

| Clase | Descripción | Ejemplo |
|---|---|---|
| `pdf_modern_unicode` | PDF digital moderno, Unicode real, texto seleccionable confiable | Koren/Steinsaltz Yevamot Part One, Part Two |
| `pdf_legacy_encoded` | PDF con encoding legacy pero decodificable mediante decoder validado | Tanaj SI-960 (Tiqwah TeX) |
| `pdf_facsimile_ocr_layer` | PDF visual/facsímil con OCR text layer. La capa textual puede tener baja calidad | HebrewBooks 34314 (iText OCR) |
| `pdf_scan_no_text` | PDF sin capa textual. Requiere OCR | — (fuera de alcance) |
| `native_digital_text` | HTML, TXT, XML, TEI, Markdown confiable de fuente digital nativa | Sefaria (futuro) |
| `manual_transcription` | Texto corregido/manual con provenance documentada | — (futuro) |
| `derived_normalized` | Texto auxiliar de retrieval (normalización lexical). Nunca canónico | `normalize_hebrew_lexical()` output |

### 3.2 `canonical_text_role`

| Rol | Descripción |
|---|---|
| `canonical_text` | Texto fidedigno, citable, persistido en PostgreSQL. Fuente de verdad |
| `facsimile_anchor` | Referencia visual de página (layout). No texto canónico |
| `retrieval_auxiliary` | Texto auxiliar para retrieval. No citable |
| `diagnostic_only` | Solo para diagnóstico técnico. No uso productivo |
| `rejected_text_layer` | Capa textual explícitamente rechazada como canónica |

## 4. Estados de promoción documental

### 4.1 Estados actuales (soportados por schema PostgreSQL)

| Estado | Descripción |
|---|---|
| `draft` | Creado, sin validación técnica |
| `test_candidate` | Aprobado para smoke/experimentos técnicos. **Estado actual de toda fuente en breslov_test** |
| `ready` | Aprobado como corpus estable |
| `archived` | Ya no activo |
| `error` | Falló en proceso de ingesta o validación |

### 4.2 Estados propuestos (documentados, no implementados en schema todavía)

| Estado | Descripción | Requisitos |
|---|---|---|
| `discovered` | Archivo localizado, sin preflight | — |
| `preflighted` | Metadata y calidad inicial evaluadas | FASE 1-2 checks |
| `test_candidate` | Permitido para smoke/experimentos | Actual |
| `approved_candidate` | Checks técnicos completos. Pendiente revisión bibliográfica | Criterios FASE 5 |
| `approved` | Aceptado como texto canónico | Criterios FASE 6 |
| `facsimile_only` | Útil como referencia visual, no texto canónico | FASE 7 |
| `rejected_text_layer` | Capa textual no confiable. Solo referencia visual | FASE 7 |
| `blocked_ocr_required` | Requiere OCR, fuera de alcance | — |
| `deprecated` | Reemplazado por fuente mejor | — |

### 4.3 Definición operativa de `ready`

`ready` es el estado operativo que significa: **documento aprobado como corpus estable interno**.

El cambio de `test_candidate` a `ready` activa:

- indexación en Milvus productivo (`tebaai_breslov_chunks_v1`);
- chunking en pipeline de producción;
- inclusión en auditorías y scripts productivos;
- participación en búsqueda sin cambios (ya visible en `test_candidate`).

`ready` **no implica**:
- exposición pública — publicación requiere decisión separada;
- texto perfecto — limitaciones se documentan en `promotion_decision.limitations_accepted`;
- inmutabilidad — puede ser reemplazado o archivado.

La promoción de `test_candidate` a `ready` sigue el workflow definido en la sección 13.

| Estado | Descripción | Requisitos |
|---|---|---|
| `discovered` | Archivo localizado, sin preflight | — |
| `preflighted` | Metadata y calidad inicial evaluadas | FASE 1-2 checks |
| `test_candidate` | Permitido para smoke/experimentos | Actual |
| `approved_candidate` | Checks técnicos completos. Pendiente revisión bibliográfica | Criterios FASE 5 |
| `approved` | Aceptado como texto canónico | Criterios FASE 6 |
| `facsimile_only` | Útil como referencia visual, no texto canónico | FASE 7 |
| `rejected_text_layer` | Capa textual no confiable. Solo referencia visual | FASE 7 |
| `blocked_ocr_required` | Requiere OCR, fuera de alcance | — |
| `deprecated` | Reemplazado por fuente mejor | — |

## 5. Criterios mínimos para `approved_candidate`

Una fuente puede promoverse a `approved_candidate` si cumple TODOS los checks
técnicos. Los checks se registran en `bibliographic_metadata` JSONB.

### 5.1 Preflight

- [ ] Archivo existe y es accesible.
- [ ] Páginas detectadas (`page_count > 0`).
- [ ] Metadata registrada (title, author, producer, creation date).
- [ ] `source_kind` clasificado explícitamente.
- [ ] `extraction_method` definido.
- [ ] No se requiere OCR. Si requiere OCR, queda `blocked_ocr_required`.

### 5.2 Extracción

- [ ] UTF-8 válido (sin errores de decodificación).
- [ ] Caracteres hebreos detectados si language=he (`hebrew_chars > 0`).
- [ ] Sin mojibake significativo (artefactos extraños < 1% de chars).
- [ ] Orden de lectura validado (muestra manual).
- [ ] Layout/columnas validado (muestra manual).
- [ ] Headers/footers no contaminan de forma destructiva.

### 5.3 Persistencia PostgreSQL

- [ ] Markdown canónico en `library_document_texts.content`.
- [ ] SHA-256 round-trip 100%.
- [ ] No se usa Milvus como fuente textual.
- [ ] `extraction_metadata` completa.

### 5.4 Chunking

- [ ] `chunks > 0`.
- [ ] `chunks_vacios = 0`.
- [ ] `avg_chunk_length` dentro de límites (200-5000).
- [ ] `page_mapping >= 95%` o justificación documentada.
- [ ] Cross-page mapping correcto si aplica.

### 5.5 Búsqueda

- [ ] FTS smoke pass para idioma esperado.
- [ ] Query negativa pass (`hits = 0`).
- [ ] OR correcto (`|`) funciona.
- [ ] `||` como OR es rechazado.

### 5.6 Embeddings (si se evalúan)

- [ ] Embeddings generados vía LiteLLM.
- [ ] Dimensión 1536.
- [ ] Milvus test collection insert/index.
- [ ] Round-trip PG↔Milvus 100%.

### 5.7 Calidad bibliográfica

- [ ] `title` presente.
- [ ] `language` definido.
- [ ] `source_type` definido.
- [ ] `source_kind` en metadata o bibliographic_metadata.
- [ ] `extraction_method` en document_texts.
- [ ] `page_refs` disponibles (page_start/page_end en cada chunk).
- [ ] `provenance` registrada (cómo se obtuvo el archivo).
- [ ] Copyright/restricciones documentadas si aplica.

## 6. Criterios adicionales para `approved`

Además de todos los checks de `approved_candidate`:

- [ ] Revisión manual de muestras por rangos (inicio, medio, final).
- [ ] Páginas complejas/columnas revisadas.
- [ ] Calidad textual aceptable para cita bibliográfica.
- [ ] No depende de OCR defectuoso.
- [ ] Metadata bibliográfica completa.
- [ ] Tests de regresión pasan.
- [ ] Decisión documentada en `docs/status_actual.md`.
- [ ] Sin bloqueo legal/operativo interno.

## 7. Política específica por tipo de fuente

### 7.1 Koren/Steinsaltz moderno (Part One y Part Two)

| Aspecto | Decisión |
|---|---|
| `source_kind` | `pdf_modern_unicode` |
| Ruta extracción | `pymupdf4llm + controlled page markers` |
| Calidad textual | Alta — Unicode real, niqqud preservado |
| Layout | Bilingüe validado. Columnas correctas |
| Estado actual | `test_candidate` (técnicamente `approved_candidate`) |
| Recomendación para producción | Aprobable como `approved`. Pendiente revisión copyright/operativa |
| Evidencia | Full pass Part One (496p, 3.28M chars) y Part Two (398p, 2.53M chars) |

### 7.2 Tanaj SI-960 (Masoretic Text)

| Aspecto | Decisión |
|---|---|
| `source_kind` | `pdf_legacy_encoded` |
| Ruta extracción | `fitz-si960 + hebrew_tex_decoder` |
| Calidad textual | Media — decoder produce algunos artefactos (`¿`, `Í` residuales) |
| Layout | Una columna. Page mapping OK |
| Estado actual | `test_candidate` |
| Recomendación para producción | `approved_candidate` técnico. Revisar artifacts residuales antes de `approved` |
| Evidencia | 200 páginas extraídas, 701K chars, decoder testeado |

### 7.3 HebrewBooks 34314 (Likutey Moharán)

| Aspecto | Decisión |
|---|---|
| `source_kind` | `pdf_facsimile_ocr_layer` |
| Capa textual: | `rejected_text_layer` |
| Rol visual: | `facsimile_anchor` |
| Ruta extracción | `fitz get_text('text', sort=True)` + page markers |
| Calidad textual | Baja — OCR artifacts, espacios excesivos, fragmentación |
| Estado actual | `test_candidate` (técnico) |
| Recomendación para producción | **No aprobar como texto canónico**. Facsímil útil para referencia visual. Si se desea texto de calidad, buscar fuente Sefaria o texto plano |
| Evidencia | Smoke 1-20 pass técnico pero calidad textual insuficiente |

## 8. Política de OCR/facsímil

- `pdf_scan_no_text` → `blocked_ocr_required`. No se procesa. Se requiere ADR OCR.
- `pdf_facsimile_ocr_layer` con text layer aceptable → `facsimile_only`.
- `pdf_facsimile_ocr_layer` con text layer defectuoso → `rejected_text_layer`.
- OCR nunca se ejecuta automáticamente. Toda decisión OCR pasa por ADR.
- Una fuente `facsimile_only` puede usarse como:
  - referencia visual para page anchor;
  - comparación con fuente textual limpia;
  - validación de page mapping.
- No puede usarse como:
  - texto canónico;
  - input de shoresh/lemas;
  - corpus de embeddings productivo.

## 9. Política de normalización lexical

- `derived_normalized` nunca es canónico.
- Normalización se aplica solo en evaluación experimental.
- No reemplaza ni sobrescribe texto en PostgreSQL.
- No se cita bibliográficamente.
- Útil para gates en hybrid retrieval.

## 10. Relación PostgreSQL / Milvus

- PostgreSQL = fuente de verdad documental. Texto literal, referencias, page mapping.
- Milvus = recuperación/ranking. Dense vectors, BM25 sparse vectors.
- Milvus nunca contiene texto canónico completo. Solo `content_preview` (200 chars).
- Todo resultado de Milvus debe resolverse contra PostgreSQL por `chunk_id`.
- Round-trip PG↔Milvus debe ser 100% para toda colección evaluada.

## 11. Checklist operativo para nueva fuente

```
□ Archivo localizado
□ Preflight ejecutado (páginas, metadata, texto seleccionable, encoding)
□ source_kind clasificado
□ Modo de extracción definido
□ Subset 1-20 extraído + verificado
□ Idioma(s) presentes
□ Layout/columnas validado
□ PostgreSQL persistido + SHA-256 round-trip
□ Chunking sin chunks vacíos
□ Page mapping >= 95%
□ FTS smoke pass
□ Query negativa pass
□ Embeddings limitados (opcional)
□ Decisión documentada en docs/status_actual.md
□ Estado asignado (test_candidate / facsimile_only / blocked_ocr_required)
```

## 12. Ejemplos históricos

| Documento | source_kind | Estado | Decisión |
|---|---|---|---|
| Koren Yevamot Part One | `pdf_modern_unicode` | `test_candidate` → `approved_candidate` técnico | Aprobable |
| Koren Yevamot Part Two | `pdf_modern_unicode` | `test_candidate` → `approved_candidate` técnico | Aprobable |
| Tanaj SI-960 Masoretic | `pdf_legacy_encoded` | `test_candidate` → `approved_candidate` técnico | Pendiente revisión artifacts |
| HebrewBooks 34314 Likutey | `pdf_facsimile_ocr_layer` | `test_candidate` (text layer `rejected_text_layer`) | No aprobar como canónico |

## 13. Workflow de promoción `test_candidate → ready`

La promoción transforma una recomendación virtual (`promotion_recommendation`) en
un cambio de estado real (`status`) aplicando un checklist y registrando la decisión.

### 13.1 Flujo

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ test_candidate│────→│  Check promoción  │────→│  ¿Checklist  │
│ + recommendation │     │  recommendation   │     │  completo?   │
└─────────────┘     └──────────────────┘     └──────┬───────┘
                                                     │
                                           ┌─────────┴─────────┐
                                           │ Sí                │ No
                                           ▼                   ▼
                                    ┌──────────────┐   ┌──────────────┐
                                    │ Dry-run       │   │ Rechazar     │
                                    │ validación    │   │ (informar    │
                                    └──────┬───────┘   │  faltantes)  │
                                           │           └──────────────┘
                                           ▼
                                    ┌──────────────┐
                                    │ ¿Apply?       │
                                    └──────┬───────┘
                                           │
                               ┌───────────┴───────────┐
                               │ Sí                    │ No
                               ▼                        ▼
                        ┌──────────────┐        ┌──────────────┐
                        │ UPDATE status │        │ Sólo dry-run │
                        │ = 'ready'     │        │ metadata     │
                        │ + metadata    │        │ registrada   │
                        └──────────────┘        └──────────────┘
```

### 13.2 Mapping recomendación → acción

| `promotion_recommendation` | Acción |
|---|---|
| `approved_candidate` | Elegible. Ejecutar checklist. Si pasa y apply → `ready` |
| `approved_candidate_conditional` | No promover. Resolver condiciones primero |
| `facsimile_only` | No promover como texto canónico |
| `rejected_text_layer` | No promover como texto canónico |
| `blocked_ocr_required` | No procesar sin ADR OCR |
| `diagnostic_only` | No promover |
| `null` | No promover (sin evaluación) |

### 13.3 Script de promoción (diseño)

El script `scripts/promote_library_document.py` (diseñado, no implementado) operará
con estas reglas:

- **Default: dry-run**. No modifica nada sin `--apply`.
- Guardrails: rechaza `canonical_text_allowed=false`, `rejected_text_layer`,
  `facsimile_only` como texto canónico.
- Registra `promotion_decision` en `bibliographic_metadata`.
- Opcionalmente cambia `status` a `ready`.

Ver diseño completo en `docs/library_promotion_workflow.md`.

## 14. Checklist de promoción

### 14.1 Obligatorios

- [ ] `source_kind` definido.
- [ ] `canonical_text_role = canonical_text`.
- [ ] `canonical_text_allowed = true`.
- [ ] `text_quality_status = pass`.
- [ ] `layout_status = pass`.
- [ ] `page_mapping_status = pass`.
- [ ] `roundtrip_sha256 = pass`.
- [ ] `chunking_status = pass`.
- [ ] `empty_chunks = 0`.
- [ ] `page_mapping_coverage >= 0.95` o excepción documentada.
- [ ] FTS smoke pass.
- [ ] Query negativa pass.
- [ ] Embedding smoke pass (si aplica).
- [ ] PG↔Milvus round-trip pass (si hay embeddings).
- [ ] Metadata bibliográfica mínima.
- [ ] `promotion_recommendation IN ('approved_candidate', 'approved')`.
- [ ] Manual review sample.
- [ ] Copyright/restricciones documentados.

### 14.2 Rechazos automáticos

| Condición | Motivo |
|---|---|
| `canonical_text_allowed = false` | Fuente no apta como texto canónico |
| `text_layer_role = rejected_text_layer` | Capa textual rechazada |
| `source_kind = pdf_scan_no_text` | Requiere OCR (ADR pendiente) |
| `source_kind = pdf_facsimile_ocr_layer` con OCR defectuoso | Texto no confiable |
| Page mapping ausente sin excepción | Sin referencias bibliográficas |
| OCR artifacts críticos (>1%) | Degradación textual |
| Texto canónico desde `derived_normalized` | Violación de política |
| Milvus-only text | Violación de fuente de verdad |

## 15. Metadata `promotion_decision`

Estructura JSONB dentro de `bibliographic_metadata`:

```json
{
  "promotion_decision": {
    "target_status": "ready",
    "decision": "approved_for_internal_corpus",
    "decision_basis": "policy_checklist_v1",
    "decided_at": "ISO_TIMESTAMP",
    "decided_by": "manual",
    "checks": {
      "source_kind": true,
      "canonical_text_allowed": true,
      "page_mapping": true,
      "fts_smoke": true,
      "embedding_smoke": true,
      "manual_review": true
    },
    "limitations_accepted": [],
    "notes": "..."
  }
}
```

Para documentos no promovidos:

```json
{
  "promotion_decision": {
    "target_status": null,
    "decision": "not_promoted",
    "reason": "rejected_text_layer",
    "notes": "Facsimile usable as page anchor only."
  }
}
```

## 16. Evaluación de fuentes actuales

| Fuente | Elegible `ready` | Estado | Acción recomendada |
|---|---|---|---|
| Koren Yevamot Part Two | Sí (técnicamente) | `test_candidate` | Dry-run. Pendiente manual review y decisión editorial |
| Tanaj SI-960 | Condicional | `test_candidate` | Resolver/aceptar artifacts residuales |
| Masoretic Text old partial | No (`diagnostic_only`) | `test_candidate` | Mantener como diagnóstico |
| HebrewBooks 34314 | No (`rejected_text_layer`) | No persistido | Facsímil. No canónico |
| Koren Yevamot Part One | Sí (si se persiste) | No persistido | Template: `approved_candidate` |

## 17. Relación con otros documentos

- `docs/library_promotion_workflow.md` — diseño completo del workflow de promoción.
- `docs/status_actual.md` — estado técnico vigente.
- `lat.md/breslov-test-corpus-policy.md` — política de aislamiento test/producción.
- `lat.md/library-retrieval-models-policy.md` — política de modelos de recuperación.
