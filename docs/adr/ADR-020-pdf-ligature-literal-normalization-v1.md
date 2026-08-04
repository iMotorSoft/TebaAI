# ADR-020 — PDF Ligature Literal Normalization V1

## Estado

Aceptado (DEV).

## Contexto

El extractor PDF de `LIKUTEY HALAJOT (Interior Final).pdf` (y de otros
documentos del corpus) emite ligaduras tipográficas Unicode de compatibilidad:

- `ﬁ` U+FB01, `ﬂ` U+FB02, `ﬀ` U+FB00, `ﬃ` U+FB03, `ﬄ` U+FB04, `ﬅ` U+FB05, `ﬆ` U+FB06;

y a veces introduce un espacio interno alrededor de la ligadura
(`reﬁ namiento` por `refinamiento`). El texto normalizado de búsqueda expande
la ligadura (NFKC) pero conserva el espacio interno, por lo que la consulta
limpia `refinamiento` no coincide de forma literal.

Caso concreto — nota 36 (página PDF 56, folio impreso 38):

- superficie extraída: `reﬁ namiento` e `Inﬁ nito`;
- consulta: `Birur hace referencia a la extracción y refinamiento de las chispas`;
- resultado anterior: la nota 36 perdía frente a evidencia semántica de otra
  obra (batch literal 24/25).

Además, el extractor intercala una glosa parentética en línea
(`Birur (pl. birurim; lit. “tamizar”) hace …`) que rompe la contigüidad del
substring para consultas largas. Los chunks de esta edición no tienen
`search_vector_es`/`search_vector_simple` (NULL), por lo que el carril literal
es la única vía de recuperación.

## Decisión

Mantener dos representaciones distintas:

- `text_original`: la superficie exacta extraída/persistida; se usa para
  citas, evidencia visible, offsets y auditoría; nunca se reescribe.
- `search_text_normalized`: forma de búsqueda; puede aplicar NFKC, colapso
  controlado de whitespace y variantes controladas de fragmentación.

Normalización canónica de búsqueda:

1. NFKC (expande ligaduras de compatibilidad);
2. expansión explícita y determinista de ligaduras residuales;
3. colapso de whitespace de presentación;
4. tratamiento de soft hyphen y caracteres zero-width solo dentro del patrón
   demostrable (SHY/ZWNJ/ZWJ no presentes en el corpus; política: no eliminar
   indiscriminadamente ZWNJ/ZWJ en hebreo/árabe sin revisar impacto);
5. variantes controladas de fragmentación: insertar el espacio de extracción
   después de un dígrafo de ligadura embebido dentro de una secuencia
   alfabética (`refinamiento` → `refi namiento`), solo para matching;
6. elisión de glosas parentéticas precedidas por letra (solo matching;
   `(Salmos 16:1)` al inicio de línea/bloque se preserva).

La regla: `normalización de búsqueda ≠ modificación del texto citado`.

## Invariantes

- La normalización no corrige ortografía (`aﬀecto` → `affecto`, nunca
  `afecto`; `oﬃcina` U+FB03 → `officina`).
- La normalización nunca une palabras reales: las variantes solo insertan
  espacios; `la flor`, `por fin`, `fi nal` permanecen separados.
- La normalización latina es independiente de la hebrea; niqqud, RTL y
  combining marks del hebreo se preservan en la cita.
- La cita original no se reescribe: el bloque canónico de la nota se cita
  completo cuando no hay mapeo exacto de offsets normalizados.
- Evidence ID determinista (derivado del chunk); estable entre repeticiones.
- La normalización es idempotente:
  `normalize_pdf_search_text(normalize_pdf_search_text(x)) == normalize_pdf_search_text(x)`.

## No decisiones

- No se reingesta el PDF.
- No se regeneran páginas, chunks ni embeddings.
- No se modifica Milvus.
- No hay OCR ni IA correctora.
- No se usa fuzzy matching como sustituto de normalización.
- No se acepta coincidencia semántica como literal.
- No se modifica metadata bibliográfica ni scope.
- No se cambia ranking para ocultar el problema.
- No se promueve `Interior Final` (sigue `test_candidate`).

## Consecuencias

- Mayor recall literal: `refinamiento` localiza `reﬁ namiento` como
  `footnote_literal_exact` (nota 36, PRIMARY estable).
- Citas fieles: la evidencia muestra la superficie original con ligaduras.
- Normalización reusable: un solo módulo
  (`pdf_ligature_normalization.py`) compartido por los carriles literales
  (notas, cuerpo, referencias), sin alterar semántica ni embeddings.
- Menor dependencia de defectos de extracción PDF.
- Necesidad de tests de offsets y de regresiones ES/EN/HE.

## Rollback

Reversión de código únicamente (funciones, SQL del carril literal, tests,
spec E2E); sin tocar datos. Ver
`data/reports/breslov/2026-08-04-pdf-ligature-literal-normalization-v1-dev/rollback-plan.md`.
