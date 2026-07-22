# Causa raíz — truncación del sujeto

`_content_subjects()` ejecutaba regex de palabras antes de consultar aliases. Para `Tisha B'Av`, obtenía `Tisha`, descartaba el token corto `B` y trataba `Av` como token posterior; el límite posicional dejaba el sujeto efectivo en `tisha`.

Después, `_compute_literal_match_kind()` contaba cantidad de variantes recuperadas en lugar de palabras dentro de la frase. Una sola variante multi-token (`Tisha beAv`) era clasificada como `single_term`, produciendo la combinación contradictoria `direct_relation + insufficient`.

Corrección: longest controlled alias antes del tokenizer, `QuerySubject.kind=named_topic` y clasificación nominal basada en frase completa.
