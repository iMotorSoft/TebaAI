# Pending evidence panel policy

During `interpreting`, `awaiting_interpretation_confirmation`, `editing_interpretation`, and `analyzing`, no analyzed response exists. `SourcePanel` receives an explicit `pendingAnalysis` state and displays:

> La evidencia verificable aparecerá después del análisis.

It does not show evidence counts, sources, a matrix, or the previous voseo instruction. Outside pending analysis, the neutral analyzed-turn copy uses `Seleccione`.
