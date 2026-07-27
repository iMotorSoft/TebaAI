# Manual review checklist

URLs:

- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research

## Test 1 — open Azamra relation

1. Enter `azamra la relaciones que tiene`.
2. Verify: `Interpreté que desea investigar con qué conceptos se relaciona Azamra.`
3. Verify only `Analizar` and `Modificar`.
4. Verify no results or sources appear.
5. Verify the source panel says: `La evidencia verificable aparecerá después del análisis.`

## Test 2 — analyze

1. Select `Analizar`.
2. Verify one analysis starts.
3. Verify the query is relational/cooccurrence for Azamra, not a literal search for the complete sentence.
4. Verify real sources and evidence IDs appear.

## Test 3 — modify

1. Start again with the focal query and select `Modificar`.
2. Replace it with `relación entre Azamra y alegría`.
3. Verify: `Interpreté que desea investigar la relación entre «Azamra» y «alegría».`
4. Verify only `Analizar` and `Modificar`, with no evidence yet.
5. Select `Analizar` and verify the binary relation runs once.

## Test 4 — another open relation

Enter `tristeza con que se relaciona`. Verify cooccurrence intent and subject `tristeza`.

## Test 5 — binary distinction

Enter `relación entre tristeza y alegría`. Verify a two-subject relation interpretation.

## Test 6 — Hebrew and mobile

Enter `עם אילו מושגים קשור אזמרה`. Verify readable RTL content, semantic button order, pending evidence copy, and analysis only after `Analizar`.
