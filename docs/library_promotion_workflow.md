# Library Promotion Workflow — TebaAI / Breslov

Estado: proposed (governance design).

Fecha: 2026-07-02.

## 1. Proposito

Definir el puente operativo entre la calidad documental (`source_quality.promotion_recommendation`)
y la promocion real de documentos (`library_documents.status`). Este documento disena el
workflow de promocion, pero no lo implementa ni aplica migraciones.

## 2. Contexto

- `library_documents.status` (constraint real): `draft`, `ready`, `test_candidate`, `archived`, `error`.
- `bibliographic_metadata.source_quality.promotion_recommendation`: estado virtual (no modifica status).
- Estados virtuales existentes: `approved_candidate`, `approved_candidate_conditional`,
  `facsimile_only`, `rejected_text_layer`, `blocked_ocr_required`, `diagnostic_only`.
- DB constraint no cambiado. No se aplico migracion.
- Tests: 113/113 PASS.

## 3. Definicion operativa de `ready`

`ready` significa: **documento aprobado como corpus estable interno**.

Consecuencias operativas:

| Aspecto | Efecto |
|---------|--------|
| Milvus productivo | Indexado en `tebaai_breslov_chunks_v1` via `index_collection()` |
| Chunking full | Procesado por `chunk_documents.py` en produccion |
| Auditorias | Incluido en `audit_bibliographic_structure.py`, `audit_page_chunk_mapping.py`, `diagnose_page_mapping_failures.py` |
| Busqueda | Retornado en resultados (sin filtro especial) — comparte espacio con `test_candidate` |
| Exposicion publica | **No implica** exposicion publica. Significa corpus interno aprobado. La publicacion requiere decision separada. |

`ready` **no significa**:
- texto perfecto sin limitaciones (las limitaciones se documentan en `promotion_decision.limitations_accepted`);
- listo para distribucion publica;
- que no pueda ser reemplazado o archivado despues.

## 4. Modelo de promocion recomendado

### 4.1 Mapeo entre estado virtual y status real

| `promotion_recommendation` | Status real sugerido | Accion |
|---|---|---|
| `approved_candidate` | `ready` | Elegible para promocion si checklist completo |
| `approved_candidate_conditional` | `test_candidate` | No promover hasta resolver/aceptar condiciones |
| `facsimile_only` | `test_candidate` o `archived` | Nunca `ready` como texto canonico |
| `rejected_text_layer` | `test_candidate` o `archived` | Nunca `ready` como texto canonico |
| `blocked_ocr_required` | `test_candidate` | No procesar sin ADR OCR |
| `diagnostic_only` | `test_candidate` o `archived` | Solo para diagnostico |
| `null` / no evaluado | `draft` | No promovible |

### 4.2 Estados operativos y su significado

| Status | Significado | Accion permitida |
|---|---|---|
| `draft` | Creado, no preflighteado | Solo diagnostico |
| `test_candidate` | Smoke/experimentos tecnicos | Chunking test, Milvus test, busqueda |
| `ready` | Corpus estable interno | Chunking prod, Milvus prod, busqueda, auditorias |
| `archived` | Reemplazado o descartado | No se procesa; se conserva registro |
| `error` | Ingesta fallida | Diagnosticar y corregir |

### 4.3 Politica por tipo de fuente

| `source_kind` | `canonical_text_allowed` | `promotion_recommendation` | Status destino |
|---|---|---|---|
| `pdf_modern_unicode` | `true` | `approved_candidate` | `ready` si checklist completo |
| `pdf_legacy_encoded` | `true` | `approved_candidate_conditional` | `test_candidate` hasta condiciones resueltas |
| `pdf_modern_unicode` | `true` | `approved_candidate_conditional` | `test_candidate` hasta condiciones resueltas |
| `pdf_facsimile_ocr_layer` | `false` | `facsimile_only` | `test_candidate` o `archived` |
| `pdf_facsimile_ocr_layer` | `false` | `rejected_text_layer` | `test_candidate` o `archived` |
| `pdf_scan_no_text` | `false` | `blocked_ocr_required` | `test_candidate` |
| `native_digital_text` | `true` | `approved_candidate` | `ready` si checklist completo |
| `manual_transcription` | `true` | `approved_candidate` | `ready` si checklist completo |
| `derived_normalized` | `false` | — | Nunca `ready`. Uso auxiliar |

## 5. Checklist de promocion `test_candidate → ready`

### 5.1 Obligatorios

- [ ] `source_kind` definido.
- [ ] `canonical_text_role = canonical_text`.
- [ ] `bibliographic_metadata.source_quality.canonical_text_allowed = true`.
- [ ] `text_quality_status = pass`.
- [ ] `layout_status = pass`.
- [ ] `page_mapping_status = pass`.
- [ ] `roundtrip_sha256 = pass`.
- [ ] `chunking_status = pass`.
- [ ] `empty_chunks = 0`.
- [ ] `page_mapping_coverage >= 0.95` o excepcion documentada.
- [ ] FTS smoke pass (terminos reales del documento).
- [ ] Query negativa pass (garbage query → 0 hits).
- [ ] OR correcto (`|`) funciona; `||` OR es rechazado.
- [ ] Embedding smoke pass (si el documento tendra vector retrieval).
- [ ] PG-Milvus round-trip pass (si hay embeddings).
- [ ] Metadata bibliografica minima (title, language, source_type, provenance).
- [ ] Copyright/restricciones documentados.
- [ ] `promotion_recommendation IN ('approved_candidate', 'approved')`.
- [ ] Manual review sample: inicio, medio, final, paginas complejas/layout.

### 5.2 Rechazos automaticos

| Condicion | Motivo |
|---|---|
| `canonical_text_allowed = false` | Fuente no apta como texto canonico |
| `text_layer_role = rejected_text_layer` | Capa textual explícitamente rechazada |
| `source_kind = pdf_scan_no_text` | Requiere OCR (ADR pendiente) |
| `source_kind = pdf_facsimile_ocr_layer` con OCR defectuoso | Texto no confiable |
| `promotion_recommendation NOT IN ('approved_candidate', 'approved')` | Recomendacion no compatible |
| Page mapping ausente sin excepcion documentada | Referencias bibliograficas no disponibles |
| OCR artifacts criticos (>1% caracteres anomalos) | Degradacion textual inaceptable |
| Texto canonico derivado solo de normalizacion auxiliar | `derived_normalized` nunca es canonico |
| Milvus-only text (no en PostgreSQL) | Violacion de fuente de verdad |

### 5.3 Decisiones condicionales

Si la promocion requiere aceptar limitaciones conocidas:

- Documentar cada limitacion en `promotion_decision.limitations_accepted`.
- Ejemplo: "artifacts `¿` e `Í` residuales en 0.3% de chars, aceptados por decision editorial".
- Las limitaciones no deben impedir citabilidad bibliografica.

## 6. Metadata `promotion_decision`

Propuesta de estructura JSONB dentro de `bibliographic_metadata`:

```json
{
  "source_quality": {
    "source_kind": "pdf_modern_unicode",
    "canonical_text_role": "canonical_text",
    "canonical_text_allowed": true,
    "text_quality_status": "pass",
    "layout_status": "pass",
    "page_mapping_status": "pass",
    "roundtrip_sha256": "pass",
    "chunking_status": "pass",
    "promotion_recommendation": "approved_candidate"
  },
  "promotion_decision": {
    "target_status": "ready",
    "decision": "approved_for_internal_corpus",
    "decision_basis": "policy_checklist_v1",
    "decided_at": "2026-07-02T12:00:00Z",
    "decided_by": "manual",
    "checks": {
      "source_kind": true,
      "canonical_text_allowed": true,
      "page_mapping": true,
      "fts_smoke": true,
      "embedding_smoke": true,
      "manual_review": true
    },
    "limitations_accepted": [
      "page_mapping_coverage 0.97 (under 0.95 threshold documented as exception)"
    ],
    "notes": "Promovido a corpus interno. Pendiente decision de exposicion publica.",
    "dry_run_verified": true
  }
}
```

### 6.1 Campos de `promotion_decision`

| Campo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `target_status` | `string` or `null` | Si | Status destino (`"ready"`, `"archived"`, o `null`) |
| `decision` | `string` | Si | `approved_for_internal_corpus`, `rejected`, `conditional`, `not_promoted` |
| `decision_basis` | `string` | Si | Version de politica usada (`"policy_checklist_v1"`) |
| `decided_at` | `string` (ISO 8601) | Si | Momento de la decision |
| `decided_by` | `string` | Si | `"manual"`, `"operator"`, `"automated"` |
| `checks` | `object` | Si | Dict de check → bool o string |
| `limitations_accepted` | `array[string]` | No | Limitaciones conocidas aceptadas |
| `notes` | `string` | No | Contexto adicional |
| `dry_run_verified` | `boolean` | No | `true` si dry-run confirmo |

### 6.2 Documentos no promovidos

```json
{
  "promotion_decision": {
    "target_status": null,
    "decision": "not_promoted",
    "reason": "rejected_text_layer",
    "notes": "Facsimile usable as page anchor only. Not eligible as canonical text."
  }
}
```

## 7. Diseno de script futuro de promocion

### 7.1 Contrato

Script: `scripts/promote_library_document.py` (no implementado, solo diseno).

Modo por defecto: **dry-run**. No cambia nada sin `--apply`.

### 7.2 Flags propuestos

| Flag | Tipo | Default | Descripcion |
|---|---|---|---|
| `--document-id` | string | obligatorio | UUID del documento a promover |
| `--target-status` | string | ready | Status destino (debe ser valido en constraint) |
| `--dry-run` | bool | `true` | Solo validar, no mutar |
| `--apply` | bool | `false` | Ejecutar promocion real |
| `--require-manual-review` | bool | `true` | Rechazar si falta flag manual review |
| `--print-checklist` | bool | `false` | Imprimir checklist sin ejecutar |
| `--write-promotion-decision` | bool | `true` | Escribir `promotion_decision` en metadata |
| `--no-status-change` | bool | `false` | Escribir decision sin cambiar status |

### 7.3 Guardrails

1. Default = dry-run.
2. No cambia status sin `--apply`.
3. Rechaza target status fuera del constraint (`draft`, `ready`, `test_candidate`, `archived`, `error`).
4. Rechaza promocion si `bibliographic_metadata.source_quality.canonical_text_allowed = false`.
5. Rechaza `text_layer_role = rejected_text_layer`.
6. Rechaza `source_kind = pdf_facsimile_ocr_layer` como texto canonico (excepto flag override).
7. Requiere checklist completo (ver seccion 5).
8. Si `--require-manual-review`, rechaza sin flag.
9. Registra `promotion_decision` en metadata.
10. Opcionalmente cambia `status` a `ready`.

### 7.4 Flujo

```
1. Validar document_id existe
2. Validar target_status en constraint
3. Cargar bibliographic_metadata
4. Ejecutar checklist contra metadata
5. Si dry-run: imprimir resultado, no mutar
6. Si apply y checklist OK:
   a. Escribir promotion_decision en metadata
   b. Si --no-status-change: solo metadata
   c. Si no --no-status-change: UPDATE status = target_status
7. Reportar resultado
```

### 7.5 Nota de implementacion

No se implementa escritura real en esta fase. El diseno queda documentado para
implementacion futura cuando se autorice la promocion.

## 8. Evaluacion de fuentes actuales

### 8.1 Koren Yevamot Part Two (`cfd5a9f9`)

| Aspecto | Valor |
|---|---|
| `source_kind` | `pdf_modern_unicode` |
| `promotion_recommendation` | `approved_candidate` |
| `status` actual | `test_candidate` |
| Chunks | 176, 0 vacios |
| Embeddings | 20, round-trip 100% |
| Page mapping | 100% |
| FTS | Pass (hebreo + ingles) |
| Query negativa | Pass |

**Elegibilidad para `ready`**: SI — cumple checklist tecnico.

**Lo que falta**:
- Manual review sample documentado.
- Decision legal/copyright.
- `promotion_decision` metadata.
- Dry-run de promocion.

**Recomendacion**: **Elegible para dry-run promotion, no auto-promovido**.

### 8.2 Tanaj SI-960 (`d48fa596`)

| Aspecto | Valor |
|---|---|
| `source_kind` | `pdf_legacy_encoded` |
| `promotion_recommendation` | `approved_candidate_conditional` |
| `status` actual | `test_candidate` |
| Chunks | 381, 0 vacios |
| Embeddings | 50, round-trip 100% |
| Page mapping | 100% |
| FTS | Pass |
| Limitaciones | Artifacts residuales (`¿`, `Í`) |

**Elegibilidad para `ready`**: CONDICIONAL.

**Condiciones pendientes**:
- Artifacts residuales deben aceptarse (documentar en `limitations_accepted`).
- O resolver decoder para los chars `KNOWN_UNMAPPED`.
- Cambiar `promotion_recommendation` a `approved_candidate` cuando se acepten.

**Recomendacion**: **No promover hasta resolver/aceptar artifacts. Mantener `test_candidate`**.

### 8.3 Masoretic Text old partial (`b62619cb`)

| Aspecto | Valor |
|---|---|
| `source_kind` | `pdf_legacy_encoded` |
| `promotion_recommendation` | `diagnostic_only` |
| `status` actual | `test_candidate` |
| Chunks | 41 |

**Recomendacion**: `diagnostic_only`, no elegible para `ready`.

### 8.4 HebrewBooks 34314 (no persistido)

| Aspecto | Valor |
|---|---|
| `source_kind` | `pdf_facsimile_ocr_layer` |
| `promotion_recommendation` | `facsimile_only` / `rejected_text_layer` |
| `canonical_text_allowed` | `false` |

**Elegibilidad para `ready`**: NO.

**Nunca `ready` como texto canonico**. Si se persiste, como `test_candidate` o `archived`.

### 8.5 Koren Yevamot Part One (no persistido)

| Aspecto | Valor |
|---|---|
| `source_kind` | `pdf_modern_unicode` |
| Template policy | `pdf_modern_unicode → approved_candidate` |
| Similitud con Part Two | Mismo pipeline, misma calidad |

**Si se persiste estable**: seria elegible para `ready` similar a Part Two.

## 9. Migracion futura necesaria

**No** se requiere migracion para este diseno. El workflow opera sobre:

- `bibliographic_metadata` JSONB (ya existe desde migracion 008).
- `library_documents.status` (constraint vigente soporta `ready`).

Si en el futuro se decide:
- Agregar estados virtuales como constraint real → requeriria nueva migracion.
- Agregar indices para `promotion_decision` → migracion de indice GIN (no requiere alter table).
- Agregar trigger de validacion → migracion de funcion/trigger.

Por ahora, el puente entre `promotion_recommendation` virtual y `status` real se
gestiona via script dry-run + actualizacion de metadata + UPDATE de status.

## 10. Estado de la ejecucion

### Completado

- ✅ Diseno del workflow de promocion (secciones 1-9).
- ✅ Script `scripts/dry_run_promotion_checklist.py` creado.
- ✅ Dry-run ejecutado para Koren Yevamot Part Two (`cfd5a9f9`).
- ✅ Resultado: 16/18 pass, 0/18 fail, 2/18 pending, 0/8 rechazos automaticos.
- ✅ Pendientes: manual review sample + decision legal/copyright.
- ✅ Documentacion actualizada.

### Proximo paso recomendado

1. Implementar `scripts/promote_library_document.py` con dry-run y `--apply`.
2. Decidir promocion real de Koren Yevamot Part Two (decision editorial/operativa).
3. Documentar `promotion_decision` en metadata de PostgreSQL.
4. Evaluar condicion de Tanaj SI-960: aceptar artifacts o mejorarlos.
5. Cerrar brecha de busqueda: evaluar si filtrar `test_candidate` en search endpoints.

## 11. Limites de este diseno

- No implementa script ni endpoint de promocion.
- No cambia status real.
- No aplica migracion.
- No toca Milvus.
- No modifica busqueda.
- No define shoresh/lemas.
- No define OCR.
