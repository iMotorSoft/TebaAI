# TebaAI — Breslov Lemma / Shoresh Layer Design

Fecha: 2026-06-30.
Estado: analysis completed.

## Objetivo

Diseñar capa experimental de lemas/raíces/shoresh artificial multilingüe para mejorar búsqueda conceptual en `breslov_test` sin modificar retrieval base.

## Corpus

| Documento | Chunks | Page refs | Idiomas |
|-----------|:------:|:---------:|---------|
| El Alma del Rebe Najmán | 476 | 273 | es |
| Kokhavey Ohr | 903 | 395 | en |
| KITZUR | 636 | 222 | es |
| **Total** | **2015** | **890** | es/en |

## Conceptos analizados (10)

| Concept ID | Query ES | Query EN | Confidence | Expansión estimada |
|-----------|----------|----------|:----------:|:------------------:|
| emunah | emuná | faith | curated | +54 chunks |
| tefillah | tefilá | prayer | curated | +68 chunks |
| teshuvah | teshuvá | repentance | curated | +63 chunks |
| hitbodedut | hitbodedut | meditation | curated | +3 chunks |
| tzadik | tzadik | righteous | curated | +87 chunks |
| yetzer_hara | yetzer hará | evil inclination | curated | +54 chunks |
| hashem | HaShem | God | curated | +60 chunks |
| rebbe_nachman | Rebe Najmán | Rebbe Nachman | curated | +96 chunks |
| simchah | simjá | joy | candidate | +90 chunks |
| bitachon | bitajón | trust | candidate | +23 chunks |

## Hallazgos

- El FTS existente encuentra resultados para todos los conceptos probados.
- La expansión multilingüe agrega chunks relevantes que la query original no captura.
- Ejemplo: "faith"/"fe" encuentran chunks en inglés (Kokhavey Ohr) que "emuná" no alcanza.
- El FTS actual (`plainto_tsquery`) no soporta booleanos OR directamente — la expansión requiere ejecutar queries individuales + merge, o migrar a `to_tsquery`.
- Vector search puede ayudar a puentear diferencias de idioma sin expansión léxica.

## Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Falsos positivos por traducción amplia | Limitar a términos curados por dominio |
| Transliteraciones ambiguas | Preferir coincidencia exacta + contexto |
| Hebreo sin niqqud genera colisiones | Solo transliteraciones curadas |
| Degradación de precisión FTS | Ponderar por confidence (curated +0.15, candidate +0.05) |
| Shoresh ≠ concepto Breslov | Conceptos curados por domain expert |

## Guardrails propuestos

1. Expansión nunca reemplaza query original
2. Términos añadidos marcados con concept_id
3. Cada resultado con chunk_id válido en PostgreSQL
4. Separar curated (score 1.0) de candidate (score 0.7)
5. Perfiles: strict (solo curated), balanced, exploratory
6. No mezclar corpus test con productivo

## Arquitectura futura propuesta

```sql
CREATE TABLE library_concept_lexicon (
  concept_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  language TEXT NOT NULL,
  label TEXT NOT NULL,
  normalized_label TEXT,
  transliteration TEXT,
  script TEXT,
  confidence TEXT CHECK(confidence IN ('curated','candidate','llm_suggested')),
  source TEXT,
  status TEXT DEFAULT 'active',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

Opcional: tabla `chunk_concepts` N:M para vinculación directa chunk→concepto.

## Tests

- `test_breslov_lemma_layer_analysis.py`: 15 tests.
- `pytest`: 419 PASS.

## Comando

```bash
uv run python -m scripts.analyze_breslov_lemma_layer --output-json /tmp/report.json
```
