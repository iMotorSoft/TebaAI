# Reproducción UI

Sesión autenticada nueva contra backend real, sin interceptar `POST /library/investigative-qa/v1`.

- Consulta: `servir a HaShem por la noche`.
- Baseline DOM: 2 elementos con texto exacto `Síntesis investigativa`.
- Final DOM: 1 elemento.
- Consola/page errors finales: 0/0.
- Fragmento completo final: 1 blockquote.
- C1 y `<#>` visibles finales: 0.
- Warning visible: 1.
- Matriz: encabezado + una fila LH.

La primera ejecución E2E también detectó y cerró un fallback frontend que prefería `snippet` crudo cuando `paragraph_text` estaba vacío.
