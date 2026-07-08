# ADR-003 - Evaluación de Milvus BM25/sparse retrieval multilingüe

Estado: proposed (experimental).

Fecha: 2026-07-02.

## Contexto

TebaAI/Breslov ya tiene tuberías funcionales para dos tipos de PDF hebreo:

1. **PDF legacy SI-960** (Tanaj): `fitz-si960` + decoder.
2. **PDF moderno Unicode** (Koren Talmud): `pymupdf4llm` + page markers.

Ambos caminos producen chunks con page mapping 100%, se persisten en PostgreSQL,
se indexan como dense vectors en Milvus y se recuperan con round-trip 100%.

PostgreSQL FTS cubre búsqueda literal. Milvus dense vectors cubren búsqueda
semántica. Pero no hay capa de recuperación lexical/bag-of-words fuera de
PostgreSQL que pueda combinarse con dense vectors en un solo ranking híbrido.

Milvus 2.6 introdujo BM25 como `FunctionType` que auto-computa sparse vectors
desde texto VARCHAR con analyzer configurable. Esto permite:

- BM25 puro (sparse retrieval).
- Hybrid dense + sparse con RRF.

## Evaluación técnica

### API disponible

| Aspecto | Valor |
|---|---|
| Milvus server | 2.6.14 |
| PyMilvus | 2.6.15 |
| `FunctionType.BM25` | Disponible |
| `DataType.SPARSE_FLOAT_VECTOR` | Disponible |
| `enable_analyzer` en VARCHAR | Requerido para BM25 |
| Index sparse | `SPARSE_INVERTED_INDEX` con `metric_type: BM25` |
| Hybrid dense+sparse | `AnnSearchRequest` + `RRFRanker` |

### Prototipo validado

Se creó colección `tebaai_breslov_bm25_test_v5` con BM25 function, se insertaron
5 documentos multilingües (hebreo, inglés, español), y se ejecutaron queries:

| Query | Resultado |
|---|---|
| `Talmud` | 1 hit score 1.41 |
| `יבמות` (Yevamot) | 1 hit score 1.30 |
| `God created heavens` | 1 hit score 4.05 (phrase boost) |
| `בראשית` (Bereshit) | 1 hit score 1.55 |
| `Breslov` | 0 hits (corpus pequeño) |
| `zzzzzzz` | 0 hits (negativa correcta) |

### Limitaciones detectadas

- `enable_analyzer` es un analyzer genérico (no específico por idioma).
- El analyzer no separa niqqud hebreo de consonantes (no es shoresh).
- La colección BM25 debe definirse al crear; no se puede agregar a colección existente.
- El sparse vector se computa automáticamente en insert; no se puede modificar después.
- No hay analyzer multilingüe oficial para hebreo; se usa el default que separa por espacios y puntuación.

## Decisión propuesta

1. **No integrar BM25 al pipeline productivo en esta fase.**
2. **Crear colección experimental** `tebaai_breslov_bm25_test_v1` (o superior) para prototipos controlados.
3. **Evaluar BM25 como capa complementaria** a PostgreSQL FTS + Milvus dense, no como reemplazo.
4. **Mantener PostgreSQL como fuente de verdad documental** — Milvus BM25 solo para ranking/recuperación.
5. **Habilitar hybrid dense+sparse** cuando el corpus de prueba tenga suficientes datos para comparación significativa.

## Alternativas consideradas

| Alternativa | Pros | Contras |
|---|---|---|
| Solo PostgreSQL FTS + trigram | Ya funciona, sin costo adicional | Sin ranking semántico, sin hybrid |
| Solo Milvus dense vector | Ya funciona para semántica | Sin recuperación lexical, puede fallar en términos raros |
| Milvus BM25 puro | Lexical multilingüe | Sin semántica, colección duplicada |
| **Milvus hybrid dense+sparse (propuesto)** | Combina lexical + semántico, ranking RRF | Complejidad adicional, dos índices |
| Elasticsearch/OpenSearch | Analyzer multilingüe maduro | Stack adicional, operación extra |
| Esperar shoresh/lemas | Solución más profunda para hebreo | No resuelve hoy |

## Criterios de comparación (futuros)

Para decidir integración productiva, se requiere evaluar:

1. Exact match hebreo (BM25 vs PG FTS vs dense).
2. Exact match inglés.
3. Consulta conceptual (dense vs hybrid).
4. Query bilingüe.
5. Query negativa.
6. Ranking: ¿BM25 mejora los top-K respecto a dense solo?
7. Latencia de indexación y búsqueda.
8. Mantenimiento de colección duplicada.

## Riesgos

1. **Analyzer único**: No hay analyzer específico para hebreo bíblico con niqqud/taamim.
2. **Duplicación de texto**: `text` VARCHAR en BM25 collection contiene el mismo texto que PostgreSQL.
3. **Drift PG↔Milvus**: Si se actualiza texto en PG, hay que re-indexar en BM25.
4. **Schema fijo**: BM25 function no se puede agregar a colección existente, requiere colección nueva.
5. **API cambiante**: Milvus 2.6 BM25 es relativamente nuevo; puede cambiar en 3.x.

## No objetivos

- Reemplazar PostgreSQL como fuente textual.
- Resolver shoresh/lemas hebreo.
- Producción inmediata.
- OCR.
- Frontend.

## Evaluación comparativa con corpus real — 2026-07-02

### Dataset

500 chunks reales de 2 documentos breslov_test: Kokhavey Ohr (EN) + Koren Yevamot (HE/EN).
Idiomas: hebreo, inglés, español.
12 queries evaluadas.

### Resultados comparativos

| Query | PG FTS | Dense | BM25 | Observación |
|---|---|---|---|---|
| `תלמוד` | 3 | 5 | 2 | BM25 encuentra hits hebreos |
| `יבמות` | 1 | 5 | 0 | BM25 no cubre término hebreo específico |
| `Talmud` | 5 | 5 | 5 | Los 3 métodos encuentran |
| `uncircumcised priest` | 5 | 5 | 0 | BM25 no tokeniza bien frase específica |
| `God created the heavens` | 1 | 5 | 0 | Dense > FTS > BM25 |
| `maravilla del cerebro` | 5 | 5 | 5 | BM25 funciona en español |
| `Breslov` | 5 | 5 | 5 | Todos encuentran |
| `zzzzzzzzzz`(negativa) | 0 | 5 | 0 | Dense siempre devuelve algo |

### Overlap análisis

| Query | Overlap BM25↔FTS | Jaccard |
|---|---|---|
| `תלמוד` | 2/3 | 0.67 |
| `Talmud` | 0/10 | 0.00 |
| `maravilla del cerebro` | 3/7 | 0.43 |
| `Breslov` | 0/10 | 0.00 |
| `Rebe Najman` | 3/7 | 0.43 |

BM25 encuentra chunks DIFERENTES a FTS para la mayoría de queries — esto sugiere que
BM25 aporta diversidad de resultados. Hybrid podría mejorar recall.

### Conclusión

**BM25 aporta valor complementario**: sus resultados tienen baja superposición con
PG FTS y dense vectors. Esto significa que un ranking híbrido (dense + sparse + FTS)
podría mejorar el recall general.

**No integrar todavía a producción**. Mantener como experimental.
El script `scripts/evaluate_bm25_retrieval.py` permite repetir la evaluación.
La decisión final queda: **seguir evaluando**.

## Hybrid/RRF evaluation — 2026-07-02

Se extendió la evaluación con `scripts/evaluate_hybrid_retrieval.py` para comparar
RRF fusion de PG FTS + Milvus dense + Milvus BM25.

### Métodos comparados

| ID | Método | Descripción |
|---|---|---|
| FTS | PostgreSQL FTS | Baseline lexical |
| Dense | Milvus dense vector (cosine) | Semantic |
| BM25 | Milvus BM25 sparse | Lexical multilingüe |
| RRF D+B | RRF dense+BM25 | Fusión sin FTS |
| RRF F+D | RRF FTS+dense | Fusión FTS+semántico |
| RRF F+B | RRF FTS+BM25 | Fusión lexical pura |
| RRF F+D+B | RRF FTS+dense+BM25 | Fusión completa |
| RRF gated | F+D+B con lexical gate | Si FTS+BM25=0, baja confianza |

### Fórmula RRF

```
score = Σ 1/(rrf_k + rank_i)  para cada método que encontró el chunk
rrf_k = 60
```

### Dataset

500 chunks reales (Kokhavey Ohr EN + Koren HE/EN).
12 queries (hebreo, inglés, español, negativa).

### Resultados

| Query | FTS | Dense | BM25 | RRF D+B | RRF F+D+B | Gate |
|---|---|---|---|---|---|---|
| `תלמוד` | 3 | 10 | 2 | 10 | 10 | 10 |
| `יבמות` | 1 | 10 | 0 | 10 | 10 | 10 |
| `מסכת` | 0 | 10 | 0 | 10 | 10 | **10 low** |
| `Talmud` | 10 | 10 | 10 | 10 | 10 | 10 |
| `uncircumcised priest` | 10 | 10 | 0 | 10 | 10 | 10 |
| `God created the heavens` | 1 | 10 | 0 | 10 | 10 | 10 |
| `teruma` | 10 | 10 | 0 | 10 | 10 | 10 |
| `maravilla del cerebro` | 5 | 10 | 10 | 10 | 10 | 10 |
| `Breslov` | 10 | 10 | 10 | 10 | 10 | 10 |
| `zzzzzzzzzz` (neg) | 0 | 10 | 0 | 10 | 10 | **10 low** |
| `Alma` | 10 | 10 | 10 | 10 | 10 | 10 |
| `Rebe Najman` | 10 | 10 | 10 | 10 | 10 | 10 |

**"low" = marcado como low_confidence por lexical gate.**

### Hallazgos clave

1. **RRF FTS+dense+BM25** da cobertura máxima (10 resultados para todas las queries).
2. **Lexical gate** funciona para negativas (`zzzzzzzzzz` → 10 low_conf) pero **sobre-flaggea**
   términos hebreos válidos que FTS/BM25 no capturan por niqqud (`מסכת` → 10 low_conf).
3. **Bigramas únicos**: RRF_FDB consolida hasta 29 chunks únicos vs 10 de cada método individual.
4. **Dense** siempre encuentra 10 resultados (incluso para gibberish) — necesita gate.
5. **FTS** es el método más selectivo pero no cubre hebreo con niqqud.

### Recomendación final

1. **No integrar RRF/hybrid a producción** en esta fase.
2. **RRF FTS+dense+BM25** es la variante más prometedora pero necesita lexical gate refinado.
3. **Lexical gate necesita analyzer mejorado** para no marcar términos hebreos válidos como baja confianza.
4. **Seguir experimental**. Script `scripts/evaluate_hybrid_retrieval.py` disponible para futuras evaluaciones.
5. **Próximo paso**: mejorar analyzer hebreo (niqqud stripping) antes de reconsiderar lexical gate.
6. **BM25 sigue siendo complementario**, no reemplazo de FTS ni dense.

## Recomendación

Mantener `scripts/evaluate_bm25_retrieval.py` y `scripts/evaluate_hybrid_retrieval.py` como herramientas experimentales.
Ampliar dataset a KITZUR ES, Tanaj HE, Breslov ES cuando estén disponibles.
Mejorar analyzer hebreo antes de re-evaluar lexical gate.
No integrar BM25 ni RRF a pipeline productivo hasta nueva evaluación.
