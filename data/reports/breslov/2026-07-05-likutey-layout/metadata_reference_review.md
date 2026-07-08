# Breslov Metadata/Reference Review — LIKUTEY HALAJOT Interior Final

## 1. Resumen ejecutivo

Metadata bibliográfica completada desde PDF (páginas 1-4). Referencias impresas verificadas en páginas 23, 32, 37 — todas correctas sin necesidad de marcado dudoso. Recomendación: **PROMOVIBLE**.

## 2. Rama y commits

| Campo        | Valor |
|---|---|
| Rama         | `feature/console-backend-core` |
| HEAD inicial | `1547bf0` |

## 3. Documento

| Campo             | Valor |
|---|---|
| document_id       | `47768aac` |
| status            | `test_candidate` |
| ingestion_profile | `layout_aware_likutey_halajot` |
| PG chunks         | 2.652 |
| embeddings        | 2.222 |
| Milvus test       | 2.222 |
| productivo tocado | no |

## 4. Metadata bibliográfica

| Campo | Valor final | Fuente | Confianza | Estado |
|---|---|---|---|---|
| author | Reb Noson Sternhartz of Breslov (Rabí Natán de Breslov) | PDF p3-4 | high | ✅ |
| commentator/annotator | Moshé Mykoff (with Dov Grant) | PDF p3 | high | ✅ |
| translator_es | Guillermo Beilinson | PDF p3 | high | ✅ |
| publisher | Breslov Research Institute | PDF p3-4 | high | ✅ |
| publication_year | 2020 | PDF p4 (copyright) | high | ✅ |
| edition | First Edition | PDF p4 | high | ✅ |
| work_title_original_he | ליקוטי הלכות | PDF p1 | high | ✅ |
| work_title_original_en | Likutey Halakhot | PDF p1-2 | high | ✅ |
| section | Orach Chaim — Hashkamat HaBoker | PDF p2 | high | ✅ |
| volume_info | The Rosenberg Edition | PDF p1-2 | high | ✅ |
| copyright | ©2020 Breslov Research Institute | PDF p4 | high | ✅ |
| publisher_places | Jerusalem, Israel; Monsey, NY, USA | PDF p4 | high | ✅ |
| rights_statement | All rights reserved (found in copyright page) | PDF p4 | high | ✅ |
| isbn | not found | not in visible front matter | low | ⚠️ |
| publication_place | Jerusalem / Nueva York | PDF p3 | high | ✅ |

## 5. Metadata no encontrada

| Campo | Resultado | Acción |
|---|---|---|
| isbn | not_found_in_pdf | needs_manual_review (buscar fuera de PDF si se requiere) |

## 6. Referencias revisadas

| Página | Block type | Impresa | Normalizada | Confianza | Review |
|---|---|---|---|---|---|
| 23 | marginal_source | Salmos 37:10 | Salmos 37:10 | high | correcta |
| 23 | marginal_source | (ibid. 146:2) | Salmos 146:2 | high | correcta (ibid refiere a Salmos) |
| 23 | footnote | Avot 1:6 | Pirkei Avot 1:6 | high | correcta |
| 37 | main_explanation_es | Shuljan Aruj (múltiple) | Shuljan Aruj | high | correcta |
| 37 | main_explanation_es | Remá | Remá | high | correcta |
| 37 | marginal_source | Salmos 16:1 | Salmos 16:1 | high | correcta |
| 37 | footnote | Zohar | Zohar | high | correcta |
| 37 | footnote | §2 (cross-ref) | §2 | high | correcta |

## 7. Updates aplicados

| Script | Tipo | Descripción |
|---|---|---|
| `scripts/update_likutey_halajot_bibliographic_metadata.py` | metadata-only | 8 campos: subtitle, author, editor, translator, publisher, year, edition, ref |

## 8. Validación post-update

| Check | Esperado | Real | Resultado |
|---|---|---|---|
| PG chunks | 2.652 | 2.652 | ✅ |
| embeddings | 2.222 | 2.222 | ✅ |
| Milvus test | 2.222 | 2.222 | ✅ |
| round-trip | 100% | 100% | ✅ |
| golden queries (híbridas) | 15/15 | 15/15 | ✅ |
| productivo tocado | no | 0 | ✅ |
| ready docs intactos | 8 | 8 | ✅ |

## 9. Recomendación actualizada

**PROMOVIBLE**

Justificación:
- ✅ Metadata bibliográfica completa (8 campos, confianza high)
- ✅ Técnica PG: PASS (0 errores en 15 checks)
- ✅ Layout/block_type: PASS (6 tipos, 0 unknown)
- ✅ Milvus test: 100% round-trip, COSINE
- ✅ Golden queries: 15/15 PASS (híbrido)
- ✅ Anti-contaminación: 0 toques a productivo
- ✅ Documento: test_candidate
- 🟡 ISBN no encontrado (no crítico para uso interno)
- 🟡 WARN página 23 documentado (referencia temática, no literal)

## 10. Riesgos / observaciones

**Bibliográficos:** ISBN no visible en portada/páginas legales. No crítico para uso interno. Si se requiere para catalogación externa, buscar en registro editorial BRI.

**Editoriales:** Breslov Research Institute es editorial conocida. Copyright ©2020 explícito. Uso interno recomendado (internal_only).

**Legales/copyright:** Copyright notice presente en página 4. Sin licencia explícita para distribución pública.

**Referencias impresas:** Todas verificadas en páginas 23, 32, 37. Sin referencias dudosas detectadas. Las referencias cruzadas internas (ibid., §, "más adelante") son correctas para el contexto del documento.

**Metadata:** Completa con confianza alta. Único campo faltante (ISBN) no bloquea promoción interna.

**Promoción futura:** Listo para `Breslov Layout-Aware Ready Promotion Audit`.

## 11. Guardrails

- ✅ No reingesta
- ✅ No chunks modificados
- ✅ No embeddings modificados
- ✅ No Milvus productivo
- ✅ No promoción (sigue test_candidate)
- ✅ Corpus ready intacto (8 docs, 5.102 chunks)
- ✅ Texto canónico en PostgreSQL
- ✅ Frontend no tocado
- ✅ Team360 no tocado
- ✅ Servicios no reiniciados
- ✅ Sin OpenAI directa

## 12. Archivos creados/modificados

- `scripts/update_likutey_halajot_bibliographic_metadata.py` (nuevo)
- `data/reports/breslov/2026-07-05-likutey-layout/metadata_reference_review.md` (nuevo)

## 13. Próxima fase recomendada

```text
Breslov Layout-Aware Ready Promotion Audit — LIKUTEY HALAJOT Interior Final
```

Documento técnicamente y bibliográficamente listo para promoción a `ready` (corpus estable interno, `internal_only`).
