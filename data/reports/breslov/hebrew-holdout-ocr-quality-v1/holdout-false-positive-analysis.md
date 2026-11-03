# False-positive analysis

0/14 rechazos negativos fallidos en este holdout. No prueba precisión full-corpus:
el lookup cerrado no reconoce ninguno de los diez pares ortográficos nuevos.
La ausencia de expansión en estos casos limita mucho el poder del test de colisiones.
Los negativos incluyen י/ו, cambio de número gramatical, ר/ד, morfología y contexto
semántico similar. Las etiquetas se definieron antes de ejecutar las reglas.

No se añadieron excepciones ni guardas manuales. Los diez fallos ortográficos se
clasifican como OUT_OF_FROZEN_LOOKUP_COVERAGE y quedan sin reparar en V1.
La dependencia MANUAL_LEXEME_ORACLE del prototipo es un riesgo adicional, no una
capability automática. Requiere V2 y nuevo holdout; no reetiquetar fallos como semantic.

Con cero errores entre 14 negativos, incluso una aproximación binomial independiente
tendría cota superior unilateral 95% ~19.3% (1 - .05**(1/14)); la independencia no está
garantizada aquí. No usar 100% observado como garantía de producción.
Semantic devuelve el target peligroso top1 en 8/14 y top3 en 12/14, sin umbral de
aceptación. Eso sería peligroso SI se promoviera similitud a equivalencia; no se hizo.

Las pruebas de prioridad son concursos aislados, no ranking PostgreSQL/Milvus.
Canónico/query se conservan; los generated_variants están separados. No se escribe corpus.
