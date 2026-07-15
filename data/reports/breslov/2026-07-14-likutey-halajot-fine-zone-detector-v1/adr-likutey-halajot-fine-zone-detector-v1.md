# ADR Fine Zone V1

La granularidad fina se modela como metadata separada y auditable, no como corpus paralelo. Cada fila exige quote, offsets y hash; el detector sólo usa regex visibles. Page-first sigue siendo la evidencia y lo no detectable sigue `page_literal_only`. IA no se usó porque los patrones eran determinísticos; cualquier caso futuro ambiguo deberá pasar por candidate store y validador.
