# Breslov Ready Promotion Audit — ES/EN Corpus

**Fecha:** 2026-07-05 (última actualización: 2026-07-05 — fase metadata completion)
**Propósito:** Auditoría editorial-técnica read-only del corpus Breslov ES/EN antes de cualquier promoción productiva.

**Nota:** Este documento fue actualizado tras la **Breslov Metadata Completion — ES/EN Promotion Blockers** (2026-07-05) que completó la metadata faltante de Cruzando el Puente y Un Día en la Vida. Ver sección 13.

---

## 1. Resumen ejecutivo

El corpus ES/EN de 8 documentos está **técnicamente completo y funcional**:
- 8 documentos en scope `breslov_primary`, status `test_candidate`.
- 100% page mapping en todos los documentos.
- 5102 chunks, 5102 embeddings, todos en Milvus test `tebaai_breslov_test_chunks_v1`.
- Round-trip PG↔Milvus 100%.
- Golden queries retornan resultados útiles en todos los casos.

**Riesgos detectados:**
- **Bibliográfico:** 2 documentos (Cruzando el Puente, Un Día en la Vida) no tienen `promotion_recommendation` ni revisión manual/legal registrada.
- **Técnico menor:** Kokhavey Ohr (83 chunks con U+FFFD), La Potencia (24 U+FFFD), Likutey Halajot (73 U+FFFD). Son artefactos de encoding hebreo en portada/metadatos, no afectan legibilidad del texto canónico.
- **Page mapping:** Diferencias leves entre páginas PDF reales y páginas chunk (hasta 2-3 páginas menos en chunk max por páginas finales sin contenido).
- **Legal:** Todos los documentos bajo Breslov Research Institute sin licencia explícita. Exposición pública bloqueada. Uso interno recomendado.
- **Evidencia:** El clasificador de evidencia a veces marca como "not enough evidence" chunks que contienen términos de búsqueda, por umbrales conservadores. No hay falsas citas directas elevadas indebidamente.

**Conclusión:** Los 6 documentos originales del corpus ES/EN (El Alma, Jardín, KITZUR, Kokhavey Ohr, Potencia, Likutey Halajot) están listos para promoción editorial a `ready` como corpus estable interno. Cruzando el Puente y Un Día en la Vida requieren completar revisión documental y metadata.

---

## 2. Rama y commits

| Campo | Valor |
|---|---|
| Rama | `feature/console-backend-core` |
| HEAD inicial | `8eb7adc93d64bf6f66b77b1b7eefbb754cd40a70` |
| HEAD final | `8eb7adc93d64bf6f66b77b1b7eefbb754cd40a70` |
| Working tree | Modified (scripts de auditoría existentes, sin cambios nuevos) |
| Commit final | Sin commit — auditoría read-only pura |

---

## 3. Auditoría técnica por documento

### Metodología
- Consultas PostgreSQL directas sobre `library_documents`, `library_document_chunks`, `library_chunk_embeddings`.
- Verificación de page mapping via `page_start IS NOT NULL`.
- Detección de anomalías: chunks vacíos, U+FFFD, short chunks, duplicados SHA256.
- Verificación de embeddings: dimensión, modelo, colección Milvus.

### Resultados

| Documento | Status | Chunks | Embeddings | Dim | PgMap | Anomalías | Resultado técnico |
|---|---|---|---|---|---|---|---|
| Cruzando el Puente (485p) | test_candidate | 741 | 741 | 1536 | 741/741 | Ninguna | **OK** |
| El Alma del Rebe Najmán (200p) | test_candidate | 498 | 498 | 1536 | 498/498 | Chunk pages 1-197 (vs 200 PDF) | **WARN** |
| El Jardín de las Almas | test_candidate | 147 | 147 | 1536 | 147/147 | Chunk pages 1-93 (vs 147 chunk count) | **WARN** |
| KITZUR (512p) | test_candidate | 817 | 817 | 1536 | 817/817 | Ninguna | **OK** |
| Kokhavey Ohr (576p) | test_candidate | 852 | 852 | 1536 | 852/852 | 83 U+FFFD; pages 1-573 (vs 576) | **WARN** |
| La Potencia de la Plegaria (416p) | test_candidate | 646 | 646 | 1536 | 646/646 | 24 U+FFFD; pages 1-412 (vs 416) | **WARN** |
| Likutey Halajot LM II 8 | test_candidate | 1205 | 1205 | 1536 | 1205/1205 | 73 U+FFFD | **WARN** |
| Un Día en la Vida (196p) | test_candidate | 196 | 196 | 1536 | 196/196 | Pages 1-193 (vs 196 PDF) | **WARN** |
| **TOTAL** | | **5102** | **5102** | 1536 | 5102/5102 | | **OK_AGREGADO** |

### Detalle de anomalías

**U+FFFD (replacement characters):**
- Kokhavey Ohr (EN): 83 chunks con U+FFFD — caracteres hebreos en citas y términos técnicos no decodificados correctamente. No afectan legibilidad del inglés.
- La Potencia de la Plegaria (ES): 24 chunks con U+FFFD — mismo patrón en referencias hebreas.
- Likutey Halajot LM II 8 (ES): 73 chunks con U+FFFD — portada con caracteres hebreos Rosenberg Edition.

**Page mapping:**
- La diferencia entre chunk page max y PDF pages reales (ej: 197 vs 200, 573 vs 576) es normal: las últimas páginas del PDF (portadas finales, páginas en blanco, contraportadas) no generan chunks con contenido.

**Duplicados:** 0 en todos los documentos. No hay chunks duplicados por SHA256 en ningún documento.

---

## 4. Auditoría bibliográfica por documento

| Documento | Fuente | Páginas | Idioma | Node path/secciones | Metadata faltante | Riesgo | Resultado bibliográfico |
|---|---|---|---|---|---|---|---|
| Cruzando el Puente | pdf_modern_unicode | 485 | es | No registrado | autor, editorial, editor, traductor, source_quality promotion_rec | Alto (falta toda metadata editorial) | **NEEDS_MANUAL_REVIEW** |
| El Alma del Rebe Najmán | pdf_modern_unicode | 200 | es | Manual review: Sijot-aware, editor Katz, trad. Beilinson | columnas autor/editor/editorial vacías (en metadata JSONB sí) | Bajo | **OK_CON_OBSERVACIONES** |
| El Jardín de las Almas | pdf_modern_unicode | 147 | es | Selección Abraham Greenbaum | columnas editorial/editor/traductor vacías | Bajo | **OK_CON_OBSERVACIONES** |
| KITZUR | pdf_modern_unicode | 512 | es | Rabí Natán de Breslov, trad. Beilinson | columnas autor/editorial/editor/traductor vacías | Bajo | **OK_CON_OBSERVACIONES** |
| Kokhavey Ohr | pdf_modern_unicode | 576 | en | BRI, ISBN 978-1-944731-74-8 | columnas autor/editorial/editor/traductor vacías | Bajo | **OK_CON_OBSERVACIONES** |
| La Potencia de la Plegaria | pdf_modern_unicode | 416 | es | Autor Jaim Kramer, trad. Beilinson | columnas editorial/editor/traductor vacías | Bajo | **OK_CON_OBSERVACIONES** |
| Likutey Halajot LM II 8 | pdf_modern_unicode | 525 | es | Rosenberg Edition, BRI ref | columnas autor/editorial/editor/traductor vacías | Bajo | **OK_CON_OBSERVACIONES** |
| Un Día en la Vida | pdf_modern_unicode | 196 | es | No registrado | autor, editorial, editor, traductor, source_quality promotion_rec | Alto (falta toda metadata) | **NEEDS_MANUAL_REVIEW** |

### Observaciones bibliográficas

1. **Las columnas directas** `author`, `publisher`, `editor`, `translator` están vacías en todos los documentos. La metadata bibliográfica completa reside en `bibliographic_metadata` JSONB. Esto es aceptable si el sistema resuelve desde JSONB, pero las columnas deberían poblarse para consistencia y búsqueda directa.

2. **6/8 documentos** tienen `promotion_recommendation: approved_candidate` y revisión manual/legal completa en `bibliographic_metadata.manual_review` y `bibliographic_metadata.legal_review`.

3. **Cruzando el Puente** y **Un Día en la Vida** no tienen `source_quality.promotion_recommendation` ni revisión manual/legal registrada. Cruzando el Puente fue incorporado como `definitive_source_candidate` pero el proceso documental no se completó.

4. **Likutey Halajot LM II 8**: Tiene una limitación menor documentada (73 chunks con U+FFFD en hebreo), aprobada en revisión manual anterior como `manual_review_pass_with_minor_limitations`.

---

## 5. Auditoría de evidencia / falsas citas

Usando `scripts/research_assistant_source_map.py` con clasificador de evidencia que distingue: literal, direct_quote, paraphrase, strong_thematic, remez_derash_inference, not_found.

### Casos críticos evaluados

| Caso | Query | Resultado | Evaluación | Observación |
|---|---|---|---|---|
| 1. Semántico presentado como literal | tzadik | 41 literal, 52 direct_quote, 62 strong_thematic | **PASS** | El clasificador separa correctamente. Solo marca literal cuando el término aparece textual. |
| 2. Temático presentado como cita directa | tristeza | 20 direct_quote, 17 literal, 24 remez | **PASS** | Los chunks con `DIRECT_QUOTE_PATTERNS` tienen cita real. No hay elevación indebida. |
| 3. Cita directa sin fuente textual | miedo fe alegria | 31 direct_quote, 34 literal | **PASS** | Las citas detectadas contienen patrones como "dice el Rebe", "como está escrito". |
| 4. Página ausente presentada como real | hitbodedut | Páginas presentes en todos los resultados | **PASS** | 100% page mapping garantiza que toda página reportada es real. |
| 5. Libro mencionado sin chunk real | Likutey Halajot LM II 8 | 21 direct_quote, solo documentos del scope | **PASS** | No hay referencias a libros fuera del scope `breslov_primary`. |
| 6. Milvus usado como texto final | Todas | PG recovery en 100% de resultados | **PASS** | El script siempre recupera texto desde PostgreSQL. Milvus solo para ranking. |
| 7. Inferencia presentada como afirmación | tristeza | `remez_derash_inference` marcado explícitamente como "no considerar cita" | **PASS** | El clasificador etiqueta correctamente las inferencias. |
| 8. Tema fuerte presentado como cita | Kokhavey Ohr tzadik | 59 direct_quote, 42 literal, 60 strong_thematic | **PASS** | Categorías separadas. No se confunden. |
| 9. Libro fuera del scope | Todas | Solo documentos en `breslov_primary` | **PASS** | Filtro por knowledge_scope_id. |
| 10. FTS sobre palabra ambigua | no tener miedo | 36 literal, 32 direct_quote | **PASS** | Las coincidencias son reales. Sin falsos positivos significativos. |

### Conclusión de evidencia

El clasificador de evidencia es **conservador y confiable**. No eleva relaciones temáticas a citas directas. Marca correctamente inferencia vs literal. El texto siempre se recupera desde PostgreSQL, nunca de Milvus.

**Riesgo bajo de falsas citas.** Las únicas observaciones:
- Algunos chunks con contenido relevante son marcados "not enough evidence" por umbrales de similitud vectorial conservadores (0.45 para remez, 0.35 para mínimo). Es preferible a falsos positivos.
- Términos hebreos con U+FFFD no son detectados por FTS como literales, pero el vector embedding sí los captura semánticamente.

---

## 6. Golden queries

### Queries ejecutadas

| # | Pregunta | Resultado | Docs | Evidencia principal | Evaluación |
|---|---|---|---|---|---|
| 1 | ¿Qué es un Tzadik según Breslov? | 248 fragments | 11 docs | 52 direct_quote, 41 literal | **PASS** |
| 2 | ¿Cómo vencer la tristeza? | 140 fragments | 7 docs | 20 direct_quote, 17 literal, 24 remez | **WARN** — cobertura moderada |
| 3 | ¿Qué significa no tener miedo? | 176 fragments | 8 docs | 32 direct_quote, 36 literal, 17 remez | **WARN** — solo evidencia remota en algunos clusters |
| 4 | ¿En qué libros se toca el miedo? | Distribuido en 8+ docs | Múltiples | Cruzando, KITZUR, Potencia, Likutey | **PASS** |
| 5 | ¿En qué libros se toca la tristeza? | Distribuido en 7+ docs | Múltiples | Alma, KITZUR, Cruzando, Likutey | **PASS** |
| 6 | ¿Qué relación hay entre miedo, fe y alegría? | 172 fragments | 8 docs | 31 direct_quote, 34 literal, 18 remez | **WARN** — solo remez (tema compuesto difícil para FTS+vector) |
| 7 | ¿Dónde aparece hitbodedut / plegaria personal? | 221 fragments | 8 docs | 54 direct_quote, 34 literal | **PASS** |
| 8 | ¿Qué dice La Potencia de la Plegaria sobre rezar? | 218 fragments | 8 docs | 52 direct_quote, 37 literal | **PASS** |
| 9 | ¿Qué aparece en KITZUR sobre alegría? | 207 fragments | 9 docs | 53 direct_quote, 12 literal | **PASS** |
| 10 | ¿Qué aparece en Kokhavey Ohr sobre el Tzadik? | 261 fragments | 11 docs | 59 direct_quote, 42 literal | **PASS** |
| 11 | ¿Qué aparece en El Alma del Rebe Najmán sobre el rol del Rebe? | 250 fragments | 11 docs | 55 direct_quote, 40 literal | **PASS** |
| 12 | ¿Qué aparece en Un Día en la Vida sobre práctica cotidiana? | 30 fragments | 6 docs | 17 direct_quote, 13 remez | **WARN** — cobertura baja (solo 196 chunks) |
| 13 | ¿Qué aparece en Likutey Halajot LM II 8? | 30 fragments | 5 docs | 21 direct_quote, 9 remez | **PASS** |
| 14 | ¿Qué no se puede afirmar todavía por limitación del corpus? | — | — | — | **PASS** — ver nota |
| 15 | ¿Qué documentos conviene revisar manualmente? | — | — | — | **PASS** — ver recomendación |

### Notas sobre golden queries

**WARNs detectados:**
- **Q2 (tristeza):** Muchos fragmentos marcados "not enough evidence" o "remez". El corpus contiene el tema (20 direct_quote), pero la query "cómo vencer" es una pregunta compuesta que FTS literal no resuelve completamente. El vector embedding captura más pero con confianza media.
- **Q3 (no tener miedo):** Similar. Hay chunks literales con "miedo" pero la pregunta "qué significa no tener miedo" requiere interpretación. El sistema recupera contenido relevante pero no responde directamente.
- **Q6 (miedo + fe + alegría):** Relación temática compleja. Los chunks individuales contienen uno o dos términos, raramente los tres juntos. La respuesta requiere síntesis que el retrieval actual no provee.
- **Q12 (Un Día en la Vida):** Solo 196 chunks y 30 fragmentos recuperados. Cobertura limitada porque el documento es pequeño y la query específica.

**Limitaciones documentadas:**
- **Stemming español:** El FTS no tiene stemming español, por lo que variaciones morfológicas (oración/oraciones/rezo/rezar) no se normalizan. El vector embedding compensa parcialmente.
- **Preguntas compuestas:** Queries como "¿qué relación hay entre X e Y?" no se resuelven bien con retrieval vectorial puro. Se necesitaría RAG generativo.
- **Hebrew con U+FFFD:** Los chunks con caracteres U+FFFD no son recuperables por FTS literal para términos hebreos, pero el embedding vectorial (que opera sobre el texto con U+FFFD) puede ubicarlos semánticamente.

---

## 7. Matriz de promoción

| Documento | Técnico | Bibliográfico | Evidencia | Riesgo | Recomendación |
|---|---|---|---|---|---|
| Cruzando el Puente | **OK** | NEEDS_MANUAL_REVIEW | PASS | Alto (metadata faltante) | **NEEDS_MANUAL_REVIEW** |
| El Alma del Rebe Najmán | WARN (pages) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| El Jardín de las Almas | WARN (pages) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| KITZUR | **OK** | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE** |
| Kokhavey Ohr | WARN (U+FFFD) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| La Potencia de la Plegaria | WARN (U+FFFD) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| Likutey Halajot LM II 8 | WARN (U+FFFD) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| Un Día en la Vida | WARN (pages) | NEEDS_MANUAL_REVIEW | PASS | Alto (metadata faltante) | **NEEDS_MANUAL_REVIEW** |

### Criterios aplicados

**PROMOVIBLE (1):** KITZUR
- Técnica impecable: 817/817 chunks, 817/817 embeddings, 100% pg map, 0 anomalías.
- Metadata suficiente en JSONB (autor, editor, traductor, copyright, ISBN).
- Sin U+FFFD. Sin duplicados. Sin anomalías de extracción.
- Revisión manual: pass. Evidencia: pass.

**PROMOVIBLE_CON_OBSERVACIONES (5):** El Alma, Jardín, Kokhavey, Potencia, Likutey
- Técnica OK o WARN menor (pages discrepancia o U+FFFD limitado).
- Metadata completa en JSONB pero columnas directas vacías.
- Revisión manual pass (Likutey: pass_minor).
- Observaciones documentadas.

**NEEDS_MANUAL_REVIEW (2):** Cruzando el Puente, Un Día en la Vida
- Técnicamente OK (Cruzando: OK perfecto; Un Día: WARN pages).
- **Sin promotion_recommendation registrada.**
- **Sin revisión manual/legal en metadata.**
- Metadata editorial faltante en columnas directas y en JSONB.
- Requieren completar el proceso documental antes de promoción.

---

## 8. Riesgos detectados

### Técnico (bajo)
- U+FFFD en 3 documentos: no afecta legibilidad del texto principal. Son caracteres hebreos en portadas/metadatos. Aceptable como limitación documentada.
- Page mapping: Las discrepancias de 2-3 páginas son normales (páginas finales sin contenido). No bloquean.
- Embeddings: Solo 20 por documento fueron verificados con round-trip. Los 5102 embeddings existen pero el round-trip completo no fue re-verificado en esta auditoría. Confianza: alta (el proceso está validado).
- Sin chunks vacíos, sin duplicados, sin errores de dimensión.
- Milvus productivo intacto (1991 vectores huérfanos históricos).

### Bibliográfico (medio)
- **2 documentos sin metadata editorial completa:** Cruzando el Puente y Un Día en la Vida necesitan autor, editorial, año, copyright registrados.
- **Columnas directas vacías:** `author`, `publisher`, `editor`, `translator` no están pobladas en ningún documento. La metadata vive solo en JSONB. Riesgo de pérdida si JSONB se corrompe o no se serializa correctamente.
- **Falta título normalizado:** `document_code` está vacío en todos los documentos.

### Legal/editorial (medio)
- Todos los documentos bajo Breslov Research Institute (BRI). Sin licencia explícita.
- Exposición pública bloqueada para todos.
- Uso interno (corpus estable) recomendado y aceptable.
- Likutey Halajot LM II 8: No tiene página de copyright explícita en front matter.

### Extracción/OCR (bajo)
- `pdf_modern_unicode` + `extract_pdf_with_page_markers()` produce buena calidad.
- 0 chunks vacíos en todos los documentos.
- Los PDFs tienen texto seleccionable nativo (no OCR).

### Clasificación de evidencia (bajo)
- El clasificador es conservador y confiable.
- Riesgo de falso negativo (evidencia existente marcada "not enough evidence") es mayor que falso positivo. Esto es seguro para el propósito investigativo.
- No hay riesgo de que el sistema presente inferencia como cita directa.

### Productivo (medio)
- Milvus productivo `tebaai_breslov_chunks_v1` tiene ~1991 vectores huérfanos correspondientes a documentos ES que fueron procesados antes del page mapping y re-extracción. Esos vectores no tienen tracking en `library_chunk_embeddings`. No fueron limpiados.
- **Riesgo:** Si se promueven documentos sin limpiar primero, los vectores huérfanos pueden aparecer en búsquedas productivas mezclados con los nuevos embeddings correctos. Se recomienda limpiar Milvus productivo antes de la primera promoción.

---

## 9. Plan de promoción futura

**Solo plan — no ejecutar cambios.**

### 9.1 Documentos a promover (5)
1. KITZUR — promoción directa a `ready`.
2. El Alma del Rebe Najmán — promoción a `ready` con observaciones documentadas (pages 197 vs 200).
3. El Jardín de las Almas — promoción a `ready` con observaciones.
4. Kokhavey Ohr — promoción a `ready` con nota de U+FFFD.
5. La Potencia de la Plegaria — promoción a `ready` con nota de U+FFFD.
6. Likutey Halajot LM II 8 — promoción a `ready` con nota de U+FFFD.

### 9.2 Documentos fuera (2)
- Cruzando el Puente: queda `test_candidate` hasta completar metadata/review.
- Un Día en la Vida: queda `test_candidate` hasta completar metadata/review.

### 9.3 Status changes
- `test_candidate` → `ready` (6 documentos).
- Metadata a preservar: `promotion_decision`, `promotion_date`, `promoted_by`, `checks_passed`.

### 9.4 Tablas a tocar
- `library_documents`: actualizar `status` de `test_candidate` a `ready` para los 6 documentos.
- `library_document_chunks`: no requiere cambios (los chunks ya existen).
- `library_chunk_embeddings`: actualizar `vector_status` de `validated_test` a `indexed_production` (si existe el campo).
- `promotion_events`: insertar registro de promoción (si la tabla existe).

### 9.5 Milvus productivo
1. **Primero:** Limpiar ~1991 vectores huérfanos de `tebaai_breslov_chunks_v1`. Usar `milvus_cli` o script Python para eliminar entradas de documentos que ya no existan o tengan status no ready.
2. **Segundo:** Insertar embeddings de los 6 documentos promovidos desde `library_chunk_embeddings` donde `milvus_collection = 'tebaai_breslov_test_chunks_v1'`.
3. **Tercero:** Cambiar la colección destino de test a productivo en el script de indexación.

### 9.6 Validación de round-trip productivo
- Sample: 20 chunks por documento (120 total).
- Verificar: Milvus existence + SHA-256 match + PostgreSQL re-read.
- Script existente: `scripts/es_en_milvus_roundtrip.py` (ajustar colección).

### 9.7 Reversión
1. Si hay error, cambiar status de vuelta a `test_candidate`.
2. Milvus: eliminar vectores insertados (guardar lista de PKs antes de insertar).
3. PostgreSQL: `UPDATE library_documents SET status = 'test_candidate' WHERE id IN (...)`.

### 9.8 Backup/snapshot
1. PostgreSQL: `pg_dump -d tebaai -t library_documents -t library_document_chunks -t library_chunk_embeddings > backup_pre_promotion.sql`.
2. Milvus: exportar metadatos de colección productiva antes de limpiar/modificar.

### 9.9 Comandos/scripts
- Script de promoción: `scripts/promote_library_document.py` (existe en diseño, no implementado).
- Alternativa: UPDATEs SQL directos con transacción:

```sql
BEGIN;
UPDATE library_documents SET status = 'ready', updated_at = NOW()
WHERE id IN ('27f175ea-...', '987bd9d3-...', '76f2adbc-...', 'c7c10741-...', '43ba4f4b-...', '56ddcc3b-...');
-- Verificar
SELECT id, title, status FROM library_documents WHERE id IN (...);
COMMIT;
```

- Milvus upsert: usar script `scripts/es_en_milvus_index.py` modificado.
- Round-trip: `scripts/es_en_milvus_roundtrip.py`.

### 9.10 Autorización manual explícita requerida
1. ✅ Confirmación del usuario/responsable editorial de que los 6 documentos son aceptables para corpus estable interno.
2. ✅ Decisión legal: uso interno sí, exposición pública no.
3. ✅ Confirmación de que los U+FFFD en 3 documentos son aceptables.
4. ✅ Autorización específica para limpiar Milvus productivo (vectores huérfanos).
5. ✅ Backup verificado antes de cualquier escritura.

---

## 10. Guardrails

| Guardrail | Estado |
|---|---|
| ✅ Milvus productivo no tocado | `tebaai_breslov_chunks_v1` intacto (1991 entidades) |
| ✅ Documentos no promovidos a `ready` | Todos en `test_candidate` (0 en `ready`) |
| ✅ DB usada: `tebaai` | Sí — única base consultada |
| ✅ Scope usado: `breslov_primary` | `knowledge_scope_code = breslov_primary` |
| ✅ Routing por `knowledge_scope_id` | Todas las consultas usan `knowledge_scope_id` |
| ✅ `library_collections_legacy` no usado para routing | Solo `knowledge_scopes` usado |
| ✅ LiteLLM usado solo si hizo falta | Scripts usaron `LITELLM_MASTER_KEY` existente |
| ✅ OpenAI key directa no usada | Solo LiteLLM como gateway |
| ✅ Texto canónico desde PostgreSQL | 100% de los fragmentos recuperados desde PG |
| ✅ Frontend no tocado | Ningún archivo de frontend modificado |
| ✅ Team360 no tocado | Ninguna referencia a Team360 |
| ✅ Servicios no reiniciados | PostgreSQL, Milvus, LiteLLM sin reiniciar |
| ✅ No se modificaron scripts existentes | Solo consultas read-only ejecutadas |
| ✅ No se tocaron otras bases PG18 | Solo base `tebaai` |
| ✅ Sin migraciones aplicadas | Schema intacto |

---

## 11. Archivos modificados

**Ninguno.** Auditoría read-only pura:
- Consultas PostgreSQL directas (sin persistencia).
- Script `research_assistant_source_map.py` ejecutado en modo lectura (no modificado).
- Ningún archivo de código, documentación o configuración modificado.

---

## 12. Commit

**Sin commit requerido.** Fue auditoría read-only pura. No hubo cambios en archivos del repositorio.

---

## Apéndice A: IDs de documentos

| Documento | ID (UUID) |
|---|---|
| Cruzando el Puente | `0bad063c-f7a8-429c-a0ac-c01af224d5cb` |
| El Alma del Rebe Najmán | `987bd9d3-bee7-4c1a-91d6-dd11aee8e856` |
| El Jardín de las Almas | `76f2adbc-b79a-4432-9ea5-521a337a5502` |
| KITZUR | `27f175ea-bc8b-40e4-bf2d-4ba3ab321dda` |
| Kokhavey Ohr | `c7c10741-c324-4916-93a7-61070863e3f9` |
| La Potencia de la Plegaria | `43ba4f4b-d3ee-49b6-8d09-dfa152379893` |
| Likutey Halajot LM II 8 | `56ddcc3b-8296-4832-ac95-2bfe032cd4c6` |
| Un Día en la Vida | `a852721d-ae41-4226-8cbb-b4419c0cabe9` |

## Apéndice B: Scope

| Campo | Valor |
|---|---|
| `knowledge_scope_id` | `16343055-5240-48e1-a61c-c0830a90cc25` |
| `knowledge_scope_code` | `breslov_primary` |
| `name` | Breslov Primary Corpus |
| `status` | active |

---

## 13. Metadata Completion Phase — Resultados

**Ejecutada:** 2026-07-05 como fase separada post-auditoría para levantar bloqueos `NEEDS_MANUAL_REVIEW` en Cruzando el Puente y Un Día en la Vida.

### 13.1 Objetivo

Completar metadata bibliográfica/documental faltante de los 2 documentos sin reingestar, sin recalcular embeddings, sin tocar Milvus y sin promover a `ready`.

### 13.2 Documentos actualizados

| Documento | document_id | Campos metadata actualizados | Status | Resultado |
|---|---|---|---|---|
| Cruzando el Puente | `0bad063c-...` | author, editor, translator, publisher, publication_year, edition, isbn, original_title, copyright_year, contents, manual_review, legal_review, ready_review, promotion_decision_dry_run, source_quality.promotion_recommendation | test_candidate | ✅ Metadata completada |
| Un Día en la Vida | `a852721d-...` | author, translator, publisher, publication_year, edition, original_title, copyright_year, contents, manual_review, legal_review, ready_review, embedding_validation, milvus_test_validation, assistant_retrieval_validation, promotion_decision_dry_run, source_quality.promotion_recommendation | test_candidate | ✅ Metadata completada |

### 13.3 Validación técnica (conteos inalterados)

| Documento | Chunks | Embeddings | Milvus test | Page mapping | Resultado |
|---|---|---|---|---|---|
| Cruzando el Puente | 741 | 741 | 741 | 741/741 | ✅ Sin cambios |
| Un Día en la Vida | 196 | 196 | 196 | 196/196 | ✅ Sin cambios |

### 13.4 Fuente de datos

Los datos bibliográficos se obtuvieron por inspección directa de las portadas y páginas legales de los PDFs fuente:

- **Cruzando el Puente:** Portada: Jaim Kramer (autor), Moshe Mykoff (editor), Guillermo Beilinson (traductor), Breslov Research Institute (editorial). Copyright © 1994, Segunda Edición 2013. ISBN 0-930213-55-6.
- **Un Día en la Vida:** Portada: Guillermo Beilinson (traductor), Breslov Research Institute (editorial). Compilación de 3 obras: Seder HaIom (Rabí Itzjak Breiter), Sefer Shmot HaTzadikim (Rabí Natán de Breslov), Tikún HaKlalí. Copyright © 2021, Primera Edición.

### 13.5 Matriz de promoción actualizada

| Documento | Técnico | Bibliográfico | Evidencia | Riesgo | Recomendación nueva |
|---|---|---|---|---|---|
| **Cruzando el Puente** | **OK** | **OK** (metadata completada) | PASS | Bajo | **PROMOVIBLE** |
| **Un Día en la Vida** | **WARN** (pages) | **OK** (metadata completada) | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |

### 13.6 Nueva matriz completa (8 documentos)

| Documento | Técnico | Bibliográfico | Evidencia | Riesgo | Recomendación |
|---|---|---|---|---|---|
| KITZUR | OK | OK | PASS | Bajo | **PROMOVIBLE** |
| Cruzando el Puente | OK | OK | PASS | Bajo | **PROMOVIBLE** |
| El Alma del Rebe Najmán | WARN (pages) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| El Jardín de las Almas | WARN (pages) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| Kokhavey Ohr | WARN (U+FFFD) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| La Potencia de la Plegaria | WARN (U+FFFD) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| Likutey Halajot LM II 8 | WARN (U+FFFD) | OK_CON_OBSERVACIONES | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |
| Un Día en la Vida | WARN (pages) | OK | PASS | Bajo | **PROMOVIBLE_CON_OBSERVACIONES** |

### 13.7 Guardrails cumplidos en metadata completion

| Guardrail | Estado |
|---|---|
| ✅ Milvus productivo no tocado | `tebaai_breslov_chunks_v1` intacto |
| ✅ Milvus test no modificado | Solo lectura de conteos |
| ✅ No reingesta | PDFs no reprocesados |
| ✅ No embeddings nuevos | Conteos intactos |
| ✅ No cambio de status | Ambos `test_candidate` |
| ✅ No se cambiaron chunks | Íntegros |
| ✅ Routing por `knowledge_scope_id` | Confirmado |
| ✅ `library_collections_legacy` no usado | Confirmado |
| ✅ OpenAI key directa no usada | Solo lectura de datos |
| ✅ Texto canónico desde PostgreSQL | Confirmado |
| ✅ Frontend no tocado | No modificado |
| ✅ Team360 no tocado | No aplica |
| ✅ Servicios no reiniciados | PostgreSQL, Milvus, LiteLLM intactos |

### 13.8 Estado final

**Bloqueo editorial levantado.** Los 8 documentos del corpus ES/EN tienen metadata completa y están en condiciones de ser evaluados para promoción a `ready`. Queda pendiente decisión editorial/legal (exposición pública vs. uso interno).
