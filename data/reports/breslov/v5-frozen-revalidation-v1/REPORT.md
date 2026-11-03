# TEBAAI_BRESLOV_V5_FROZEN_REVALIDATION_V1

## GATE RESULT

**BLOCKED**

No se creó ni selló un holdout nuevo, no se abrió V5, no se ejecutaron las
regresiones del gate, no se hizo commit y no se hizo push.

## Base

- Branch: `feature/console-backend-core`
- Base HEAD: `704ae24597e916b56ddec8a71fd0a30d34793aab`
- Source PDF: `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf`
- Source SHA-256: `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
- Physical pages: 284

## Blocker

La revalidación exige un holdout completamente disjunto de
`ALL_PREVIOUSLY_OPENED_PAGES` con al menos 2 continuaciones cross-page
verdaderas descubiertas solo por fuente. El corpus no ofrece ese material.

Inventario:

- Páginas previamente abiertas: 198.
- Páginas no abiertas: 86.
- Páginas no abiertas con notas: 19.
- Pares consecutivos no abiertos con notas en ambas páginas: 3.
- Continuaciones cross-page verdaderas en esos 3 pares: 0.

Los únicos pares consecutivos con ambas páginas no abiertas y notas son:

| Par | Última línea de nota en origen | Primera línea de nota en destino | Resultado |
| --- | --- | --- | --- |
| 156 -> 157 | `34 En §5 de la lección del Rebe.` | `35 La revelación de MaLJut ...` | Sin continuación: nota 34 cerrada; nota 35 marcada. |
| 157 -> 158 | `con la boca para estudiar y enseñar Torá (ver Maharsha, loc. cit.).` | `38 El Rebe trata esto en profundidad en el LM I, 22:5, donde` | Sin continuación: nota 37 cerrada; nota 38 marcada. |
| 209 -> 210 | `versículos.` | `23 Ver §9 de la lección del Rebe (también §11 más adelante)` | Sin continuación: nota 22 cerrada; nota 23 marcada. |

Sí existen continuaciones verdaderas en el PDF, pero todas requieren al menos
una página ya abierta y por tanto no son elegibles. Ejemplos verificados:

| Par | Página abierta | Evidencia |
| --- | --- | --- |
| 44 -> 45 | 45 | 44 termina nota 12 en `El`; 45 comienza con `tormento del alma...` sin marcador. |
| 78 -> 79 | 78 | 78 termina nota 86 en `Korbán`; 79 comienza con `Pesaj...` sin marcador. |
| 133 -> 134 | 133 | 133 termina en `...fuerzas destructoras`; 134 comienza con `que gobiernan...` sin marcador. |
| 140 -> 141 | 140 | 140 termina en `La expansión`; 141 comienza con `de los jasadim...` sin marcador. |
| 210 -> 211 | 211 | 210 termina en `cuya guía`; 211 comienza con `moral instila...` sin marcador. |
| 16 -> 17 | Ambos | Positivo de desarrollo. |
| 56 -> 57 | Ambos | Positivo de desarrollo. |
| 167 -> 168 | Ambos | Positivo de desarrollo. |
| 206 -> 207 | Ambos | Positivo de desarrollo; link históricamente verdadero. |

Por tanto, un holdout nuevo solo podría ser safety-only con 0 positivos nuevos.
Eso repetiría exactamente la falla metodológica del V5 anterior, que el pedido
prohíbe expresamente. No se construyó un holdout safety-only porque consumiría
páginas sin producir evidencia de utilidad y no podría emitir PASS.

## Qué no se ejecutó

- No se creó `frozen-candidate-manifest.json` con semántica de freeze de gate.
- No se creó `frozen-gate-contract.json`.
- No se creó `holdout-definition.json`.
- No se creó `holdout-seal.json`.
- No se abrió V5 sobre un holdout nuevo.
- No se corrieron regresiones de desarrollo, permutation, consumer, worker ni
  suite backend completa para este gate.
- No se modificó código de producción.
- No se hizo commit.
- No se hizo push.

Los hashes de los candidatos V5 se registran solo como evidencia de estado, no
como freeze aprobado:

```text
afdc4a994c9a299aecc5c208bbdeedd657f9e4e74f483ba58ab171affbd7257a  automatic_region_certification_v5.py
1c7e284516361f375ddbba7fd010aa49d658910381f000634a7231760e548965  automatic_region_certification_v4.py
4b0291fab84ce623098c89b12e24e2fc9174ade1922f275310c77e07d0b9eb7b  region_markdown_provenance.py
92498521ff30c9cc639a1e6667aac6aa6469b52b9269cd7cecd2a6cdbbf00454  extractors.py
5f8ac9975b5f2c929a454e0c2f718748b1b325d95af944f8a70d1e4da7d31ef0  annotation_preseal_validation.py
a0cc29a4a52335ec86345d820efdb6df9d45ddab2ec99852e78ca04d0bc513c2  test_automatic_region_certification_v5.py
ecd442dc0a10f45d6882b444a37981aec4cf5005637c78c3b8094538467708cb  test_consumer_region_certificates_v5.py
e16f8fa82928847ca9e05ebbb4315f1601ec7e9e337843ca11ffeb167ea74f96  test_annotation_preseal_validation.py
4020d9453939acc93b9e84a1e62c26ca4d80a932f97955e8a2f29395ab6899b5  evaluate_holdout.py
```

## Decisión

`COMMIT=NO`, `PUSH=NO`, `REMOTE_HEAD_CHANGED=NO`.

El remoto debe permanecer en `704ae24597e916b56ddec8a71fd0a30d34793aab`.
