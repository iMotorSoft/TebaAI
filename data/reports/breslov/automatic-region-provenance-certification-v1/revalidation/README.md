# Revalidación del worktree recibido

```text
TEBAAI_BRESLOV_AUTOMATIC_REGION_PROVENANCE_CERTIFICATION_V1_FAIL
READY_FOR_C_REINGEST = NO
```

Al iniciar esta sesión ya existían la implementación automática, sus tests y
el informe V1 completo, incluido el holdout abierto con cinco falsas
certificaciones. Esta sesión NO implementó esos archivos ni ajustó las reglas.
Se preservaron todos los archivos preexistentes por comparación SHA-256.
No se reutiliza el holdout abierto para diseñar nuevas reglas V1.

## Validación ejecutada en esta sesión

- Focal: **91 passed, 0 failed** (`focal.txt`).
- Extracción/editorial/library/content ingestion relacionada: **613 passed,
  0 failed** (`related.txt`).
- Backend completo: **1775 passed, 18 failed, 94 warnings** (`full.txt`).
- Los detalles completos de los 18 fallos son byte-idénticos al log final V1,
  que a su vez coincide con el baseline anterior a la implementación.
  Clasificación heredada y corroborada: 18 PREEXISTING_BASELINE_FAILURE;
  ninguna CURRENT_REGRESSION observada. No se afirma causa ambiental.
- Evaluador ejecutado nuevamente sobre el PDF real, sin certificados manuales,
  redirigiendo sus salidas a un directorio temporal para no sobrescribir V1.
  Los JSON de 167/55/56, holdout, estabilidad y resumen son byte-idénticos.
- Tres nuevas extracciones producen los mismos certificados.
- `git diff --check`: PASS. Diff de extracción revisado: la API opt-in ya estaba
  presente al inicio; no se modificó código en esta sesión.

## Resultado funcional corroborado

| Propiedad | Resultado |
|---|---|
| Descubrimiento automático de regiones | YES, subconjunto |
| Provenance automático | YES, subconjunto; emisor no seguro globalmente |
| Zonas body certificadas | NO |
| Zonas note certificadas | YES, subconjunto etiquetado |
| Column ownership | YES, columnas de notas soportadas |
| Corrupción identificada automáticamente | YES, diferencial nativo/layout soportado |
| ACCEPTED vs PLATFORM_EXTRACTION_ERROR | YES, subconjunto con evidencia |
| Casos ambiguos fail closed globalmente | NO, cinco zonas falsas |
| 167 PARTIAL automático | YES, pero cuerpo y todas las notas no cumplen |
| 55 ambos vecinos certificados | NO |
| 56 límites editoriales completos | NO, continuación en 57 no resuelta |
| Unsafe false certifications | 5 / 148 regiones de 12 páginas holdout |
| Certificados listos para worker | NO |

Los resultados detallados por página, anotación y contrato siguen en el
[informe V1](../README.md). No se declara BLOCKED: hay geometría e identidad;
la capability implementada falla sus criterios, no una barrera irreversible.

## Git y operaciones

Branch: `feature/console-backend-core`.
HEAD inicial/final: `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Archivos modificados por esta sesión: ninguno preexistente.
Archivos añadidos: únicamente este subdirectorio `revalidation/`.
Commit = NO; push = NO; worktree preexistente preservado = YES.
OCR = NO; SI-960 = NO; worker enforcement = NO; C reingest = NO;
PostgreSQL writes = NO; Milvus writes = NO; publication = NO;
production changes = NO; servicios gestionados = NO.

Riesgo: confundir tests verdes de contrato con certificación funcional segura.
Próximo paso: V2 de zonas/dirección/continuaciones con un holdout nuevo sellado;
NO reabrir todavía el gate del worker. No se entrega PASS incompleto.
