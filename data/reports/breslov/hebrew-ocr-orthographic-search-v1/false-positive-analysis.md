# Precisión / falsos positivos

17 casos: 11 positivos (8 candidatos מלא/חסר + 3 controles), 6 negativos reales. Queries modernas son candidatas del benchmark; no se afirma que ambas grafías estén atestiguadas en la misma edición.

| Par peligroso | Por qué no expandir |
|---|---|
| לנגדי / לנגד | sufijo posesivo |
| בעצמו / בעצמי | persona gramatical |
| מימיני / ממנו | significado/referencia distinta |
| שהיא / שהוא | género |
| אותו / את | pronombre / marcador de objeto |
| יכול / כל | verbo / cuantificador |

Todos colisionan al quitar indiscriminadamente י y ו. La cascada léxica experimental rechaza 6/6. Ninguna regla `ignore י/ו`, stems o prefijos implícitos existe en el prototipo.

**Límite decisivo:** las entradas y guardas de lexema/contexto fueron curadas sobre el mismo conjunto usado para medir. `confirmed_context` es una anotación de revisión, NO un desambiguador automático implementado. 0/6 falsos positivos no prueba precisión general; con sólo 6 negativos, la cota superior Wilson 95% de la tasa es ~39%. No cerrar un gate universal ni aprobar una expansión global por este dato.

`פירוש → פרוש` puede recuperar la interpretación en el source pointed/contexto del versículo. `פרוש` aislado también puede representar otra palabra/vocalización. Sin guarda confirmada, se puede generar candidato, pero el helper NO lo acepta como match ortográfico. Un test lo verifica. No existe identidad semántica absoluta.

Embeddings reales sobre los snippets: positivos 10/11 top1 y 11/11 top3; **negativos 5/6 top1, 6/6 top3**. Son candidatos semánticamente cercanos pero lexicalmente incorrectos, no falsos matches literales aceptables. No usar cosine como certificado de grafía o de cita. `תפילה` rankea `תפלין` antes que `תְּפִלָּה`: expansión controlada podría mejorar precisión/ranking, no sólo recall top-k.

No hay prueba ANN/Milvus sobre corpus completo, holdout lingüístico, colisiones same-key ni expansión afijada certificada. Próxima evidencia mínima: holdout independiente de las 8 entradas, distractores con distintas vocalizaciones/sentidos, query de frases reales y ranking en un snapshot read-only. Hasta entonces: **MORE_EVIDENCE**, no correcciones silenciosas.
