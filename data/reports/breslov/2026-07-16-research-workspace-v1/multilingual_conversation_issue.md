# Comprensión conversacional multilingüe

Fecha de cierre técnico: 2026-07-18.

## Reproducción

La consulta `אתה מחפש איפה נמצא מושג העקרב.` llegaba al retrieval como una frase literal completa. El clasificador anterior reconocía hebreo, pero no separaba la instrucción `אתה מחפש איפה נמצא מושג` del sujeto `העקרב`; por ello SQL/FTS buscaban la oración y devolvían cero evidencias.

## Causa raíz

El endpoint tenía extracción especializada para frases literales y copy/paste de PDF, pero carecía de un contrato estructurado que distinguiera concepto, frase, referencia, relación y follow-up en ES/EN/HE. Además, la interpretación generativa existente sólo aportaba redacción y no un objeto validado que pudiera gobernar un plan de retrieval seguro.

## Corrección

Se incorporó preprocesamiento Unicode, interpretación estructurada opcional vía LiteLLM, validación Pydantic estricta, fallback determinístico, morfología hebrea prudente y mapping por intent hacia el retrieval PostgreSQL existente. La IA no aporta IDs, páginas, fuentes, SQL ni evidence strength. El backend vuelve a derivar todas las variantes y valida cada evidencia contra el corpus.

El caso principal ahora produce `language=he`, `intent=concept_lookup`, sujeto exacto `העקרב`, normalizado `עקרב`, y consulta primero ambas formas. La traducción `escorpión` es sólo una expansión secundaria etiquetada.

## Resultado

- batch multilingüe: 30/30;
- variantes hebreas: 7/7;
- negativos: 10/10;
- integración IA real: 5/5;
- HTTP autenticado real: 15/15;
- E2E principal, mixto, intents, follow-up, copy/paste, responsive y Axe crítico: PASS.

No se modificó el texto canónico ni se reingestó el corpus.
