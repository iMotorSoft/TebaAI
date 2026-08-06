# Kitzur Likutey Moharán — Nivel 3: Preguntas de Síntesis

Fecha: 2026-07-12. Modalidad: terminal, consultas de sólo lectura.

## Resumen ejecutivo

| # | Pregunta | Estado | Evidencia | Observaciones |
| - | -------- | ------ | --------- | ------------- |
| 1 | Teshuvá | PASS | páginas 20–33, 65–66 y 204–205 | El proceso escalonado está explícito. |
| 2 | Pureza sexual | PASS | 17, 36, 81–82, 136–145 | Medios y consecuencias aparecen en páginas distintas. |
| 3 | Plegaria perfecta | PASS | 17–18, 25, 41, 60–61 | Las páginas 292–293 y 331–332 no se usaron como citas finales. |
| 4 | Hitbodedut | PASS | 65–66, 202–203, 237, 466 | Definición, práctica y efectos están literalmente atestiguados. |
| 5 | Shabat | PASS | 159–160, 341, 343–344, 404, 461–462 | La relación fe–bendición–alegría es textual. |
| 6 | Punto bueno / nekudá tová | PASS | 407–409 y 411 | Lección 282; página 410 no añadió evidencia independiente. |
| 7 | Temor perfecto y ángeles | PASS | 419–424 | La cadena causal está condensada de forma particularmente clara. |

## Metodología

- Corpus efectivo: **Kitzur Likutey Moharán**, español, `breslov_test`, run `492acd8d-06bd-42ac-a511-f3ec52f97bb3`. No es el corpus productivo `breslov_primary`: por lo tanto esta evidencia es candidata/investigativa y no una promoción de corpus.
- PostgreSQL fue la fuente textual final: `library_pages_v2`; se verificaron 57 páginas esperadas con variantes españolas y se seleccionaron los pasajes siguientes.
- Se ejecutó el validador read-only `scripts.ingestion_v2_kitzur_validate`: PASS (512 páginas, 506 con texto, 361 secciones, 19 menciones de concepto, 11 referencias y 10 relaciones).
- Se ejecutó `scripts.book_qa_v2_hybrid_probe` para `hitbodedut + plegaria`: PostgreSQL + Milvus + LiteLLM funcionaron; los candidatos fueron rehidratados desde PostgreSQL. La colección usada fue la aislada `tebaai_breslov_bookqa_v2_kitzur_test_pages_v1`.
- Se ejecutaron siete llamadas HTTP a Book QA V2. El lote obtuvo 29/175 porque el clasificador actual no descompone preguntas largas de síntesis; esos resultados no se tomaron como falta de texto. Se usó su capa SQL equivalente, por términos y página, para verificar las citas.
- Relation QA no se usó como evidencia final: su contrato operativo está orientado a `breslov_primary`; no se amplió el scope ni se mezcló el candidato Kitzur con el corpus productivo.
- Idioma: español primero. No se halló en este run una fuente inglesa o hebrea paralela que sustituyera las citas españolas.

## Pregunta 1 — Teshuvá

### Síntesis

El proceso se presenta como una práctica continua de humildad, confesión y juicio. La persona acepta el agravio sin responder; se confiesa verbalmente ante un estudioso de Torá; se examina en hitbodedut; y llega a la vergüenza que el texto identifica con la esencia del arrepentimiento. No es una etapa única: aun el arrepentimiento anterior debe ser revisado desde una percepción más alta. Para sostener el movimiento de elevarse y retornar, el texto exige pericia en la ley; Keter aparece como nombre de ese arrepentimiento esencial.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Confesión verbal ante estudioso de Torá | Kitzur Likutey Moharán | 20–21 | “Este conocimiento se alcanza mediante la confesión verbal delante de un estudioso de Torá”. | literal |
| 2 | Humildad, silencio e insultos | Kitzur Likutey Moharán | 29, 33 | “la esencia del arrepentimiento se manifiesta cuando la persona oye que la avergüenzan… en silencio”. | literal |
| 3 | Arrepentirse también de lo ya arrepentido | Kitzur Likutey Moharán | 30–31 | “uno debe arrepentirse de su arrepentimiento anterior”; el Tzadik continúa arrepintiéndose de sus previas concepciones. | literal |
| 4 | Correr y retornar | Kitzur Likutey Moharán | 31–32 | “deberá ser muy experta en la ley judía” para no ser alejada al elevarse o caer. | paráfrasis cercana |
| 5 | Juicio, vergüenza y Keter | Kitzur Likutey Moharán | 65–66, 204–205 | “La vergüenza es la esencia del arrepentimiento”; en 33 el arrepentimiento es “el concepto de Keter”. | literal |

### Notas investigativas

- La página 33 confirma Keter; las páginas 204–205 confirman vergüenza y perdón. No se localizó una forma española estable de EHIéH/Eheyeh en los pasajes seleccionados, por lo que no se fuerza esa asociación como cita literal.

## Pregunta 2 — Pureza sexual

### Síntesis

La pureza sexual se describe como santidad que se cultiva mediante el habla/Lenguaje Sagrado, el apartamiento consciente de pensamientos lujuriosos y el resguardo de la mirada mediante tzitzit. No se presenta sólo como abstención: se vincula con la plegaria, el refinamiento de la voz y sabiduría, el sustento y rúaj hakodesh.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Lenguaje Sagrado | Kitzur Likutey Moharán | 81–82 | “La pureza sexual es la esencia de la santidad” y se alcanza “mediante el lenguaje sagrado y el habla sagrada”. | literal |
| 2 | Tzitzit y mirada | Kitzur Likutey Moharán | 36 | “La inmoralidad sexual depende principalmente de los ojos” y tzitzit es “rectificación y protección”. | literal |
| 3 | Apartar la mente | Kitzur Likutey Moharán | 140 | Al advertir pensamientos lujuriosos, “quebrar sus deseos y alejar la mente” constituye su esencia. | literal |
| 4 | Plegaria y voz/sabiduría | Kitzur Likutey Moharán | 17, 136–137 | “Aquel que cuida la pureza sexual se vuelve digno de orar”; obtiene voz refinada para “cantar y para orar”. | literal |
| 5 | Rúaj hakodesh y sustento | Kitzur Likutey Moharán | 82, 145 | Conexión con “espíritu sagrado de profecía”; el sustento puede llegar “sin esfuerzo”. | literal |

### Notas investigativas

- La fórmula “rectificación del brit” aparece como contexto interpretativo; las citas finales sostienen los medios concretos sin atribuir un mecanismo adicional no textual.

## Pregunta 3 — Plegaria perfecta

### Síntesis

La plegaria perfecta empieza por decir las palabras con honestidad incluso en oscuridad. Requiere cuidado de la pureza sexual, unión con los Tzadikim que elevan la plegaria y una práctica alegre. La meta es una paz que vincula cuerpo, alma y todos los mundos; el orgullo y los pensamientos ajenos son obstáculos que el texto exige superar, no simples rasgos accesorios.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Sinceridad y verdad | Kitzur Likutey Moharán | 41 | Debe decir las palabras “con honestidad”, aun en profunda oscuridad. | literal |
| 2 | Condición y Tzadikim | Kitzur Likutey Moharán | 17–18 | “Es imposible alcanzar una plegaria perfecta” sin ese cuidado; hay que unirla a los “verdaderos Tzadikim”. | literal |
| 3 | Alegría | Kitzur Likutey Moharán | 25 | La mitzvá se realiza “con una gran alegría” y desde allí se sabe cómo orar por el mundo. | literal / temática |
| 4 | Obstáculos | Kitzur Likutey Moharán | 17 | Caridad previa salva de “pensamientos ajenos” y permite orar sin desviarse. | literal |
| 5 | Culminación | Kitzur Likutey Moharán | 60–61 | Por la plegaria se llega a “la paz general” o paz en todos los mundos. | literal |

### Notas investigativas

- “Cada palabra abraza el alma” no fue encontrado literalmente; la unidad interior se expresa aquí mediante la paz entre cuerpo y alma. Se conserva como paráfrasis, no como cita.

## Pregunta 4 — Hitbodedut

### Síntesis

Hitbodedut es conversación personal y juicio de sí delante de Dios. En ella se derrama el corazón, se revisan actos y se elevan los temores caídos. El texto sitúa como ideal la noche y un lugar apartado; además la presenta como autoanulación e inclusión en la fuente. El idioma familiar, el examen y la vergüenza conforman una práctica concreta, no sólo una noción contemplativa.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Conversación y juicio | Kitzur Likutey Moharán | 65–66 | “hitbodedut y la conversación con el Creador” donde se “evalúa y se juzga a sí misma”. | literal |
| 2 | Temores y luz oculta | Kitzur Likutey Moharán | 65–66 | De ese juicio “se eliminan todos los temores”; para la “luz oculta” debe dedicar mucho tiempo a hitbodedut. | literal |
| 3 | Vergüenza | Kitzur Likutey Moharán | 202–203 | El reconocimiento de las transgresiones lleva a “una gran vergüenza delante de Dios”. | literal / temática |
| 4 | Noche, lugar y fuente | Kitzur Likutey Moharán | 237 | “La única manera” de inclusión en la fuente es hitbodedut; el momento ideal es la noche y el lugar, fuera de zonas habitadas. | literal |
| 5 | Idioma cotidiano | Kitzur Likutey Moharán | 466 | Debe expresarse ante Dios “en el idioma que les sea más familiar”. | literal |

### Notas investigativas

- La idea de llevar el mundo al bien aparece en otros pasajes de pureza sexual; no se la atribuye como efecto literal exclusivo de hitbodedut.

## Pregunta 5 — Shabat

### Síntesis

Shabat funciona como encarnación de la fe y culminación de bendiciones. Da daat y compasión; su comida es un modo de santidad y de honor; el alma adicional intensifica la sensibilidad del día. La alegría de Shabat completa la comprensión, trae libertad y eleva los temores caídos, de modo que rectificación y alegría quedan unidas en prácticas concretas.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Fe y bendición | Kitzur Likutey Moharán | 159–160 | Shabat es “manifestación y encarnación de la fe” y las bendiciones “sólo se completan” allí. | literal |
| 2 | Daat y compasión | Kitzur Likutey Moharán | 341 | “En Shabat, cada persona se impregna de conocimiento sagrado (daat)” y se fortalece la compasión. | literal |
| 3 | Comida y alma adicional | Kitzur Likutey Moharán | 343–344, 404 | Comer en Shabat es “pura Divinidad y santidad”; aparece el “alma adicional”. | literal |
| 4 | Alegría, libertad y temor | Kitzur Likutey Moharán | 461–462 | “Mediante la alegría del Shabat” hay libertad, comprensión completa y elevación de “temores caídos”. | literal |

### Notas investigativas

- La referencia a los pies (p. 328) no fue necesaria para sostener la síntesis principal; permanece como apoyo de rectificación del caminar espiritual.

## Pregunta 6 — Punto bueno / nekudá tová

### Síntesis

La Lección 282 enseña a buscar de modo reiterado un punto bueno aun dentro de una situación mezclada con impureza. Ese hallazgo mueve del lado de culpa al mérito, devuelve vida y alegría y hace posible la plegaria. El líder de oración, además, reúne los puntos buenos de la congregación. La enseñanza se articula con juzgar favorablemente; no es una negación del mal, sino un criterio para encontrar un bien verificable.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Buscar reiteradamente | Kitzur Likutey Moharán, Lección 282 | 407 | “continuar buscando… hasta encontrar más puntos buenos”. | literal |
| 2 | Vida, alegría y plegaria | Kitzur Likutey Moharán, Lección 282 | 407–408 | El hallazgo permite “darse vida y alegría” y “orar como debe”. | literal |
| 3 | Dimensión comunitaria | Kitzur Likutey Moharán, Lección 282 | 409 | El líder debe “recolectar todos los puntos buenos” de quienes oran. | literal |
| 4 | Juicio favorable | Kitzur Likutey Moharán, Lección 282 | 407 | Al hallar mérito, se traslada “del lado de la culpa hacia el lado del mérito”. | paráfrasis cercana |

### Notas investigativas

- “Evitar depresión” es una inferencia editorial moderada de dar vida, animarse y orar con alegría; no se presenta como una cita literal de la palabra depresión en estos pasajes.

## Pregunta 7 — Temor perfecto y dominio sobre ángeles

### Síntesis

La secuencia es explícita: el dominio durable sobre los ángeles requiere temor perfecto asentado en el corazón. Los deseos de dinero, placer sexual y comida lo dañan; Pesaj, Shavuot y Sukot rectifican respectivamente esos deseos. Con temor perfecto se alcanza plegaria perfecta y se eliminan características que impiden orar; entonces las huestes celestes se subordinan. El cierre no es individualista: el temor permite reconocer y unirse a líderes verdaderos, y por ellos a las almas de Israel.

### Proceso paso a paso

| Paso | Enseñanza | Fuente | Página | Evidencia | Tipo |
| ---- | --------- | ------ | ------ | --------- | ---- |
| 1 | Finalidad y temor | Kitzur Likutey Moharán, Lección 1 | 419–420 | “El judío fue creado para tener dominio sobre los ángeles”; se requiere “perfecto temor a Dios”. | literal |
| 2 | Tres deseos | Kitzur Likutey Moharán, Lección 1 | 420 | Dinero, placer sexual y comida “socavan y dañan el temor a Dios”. | literal |
| 3 | Tres Festividades | Kitzur Likutey Moharán, Lección 1 | 421 | Pesaj rectifica dinero; Shavuot, placer sexual; Sukot, comida. | literal |
| 4 | Plegaria perfecta | Kitzur Likutey Moharán, Lección 1 | 422 | Rectificar los deseos lleva a “temor perfecto a Dios y la plegaria perfecta”. | literal |
| 5 | Subordinación y líderes | Kitzur Likutey Moharán, Lección 1 | 423–424 | “todos los ángeles superiores se subordinan”; unirse a líderes verdaderos une a las almas y hace perdurar el dominio. | literal |

### Notas investigativas

- La inspiración profética aparece en la p. 423 junto con temor, festividades y plegaria; la lista de tres rasgos negativos se menciona como condición general, pero no se transcribe aquí sin un fragmento completo que los enumere.

## Hallazgos multilingües

| Pregunta | Español | Inglés | Hebreo | Nota |
| -------- | ------- | ------ | ------ | ---- |
| 1–7 | Sí, fuente principal | No usado como sustituto | No usado como sustituto | El run Kitzur consultado es español; se preservan `teshuvá`, `hitbodedut`, `tzitzit`, `Keter`, `daat`, `rúaj hakodesh` y `nekudá tová`. |

## Validación

Comandos principales:

```bash
./SrvRestAstroLS_v1/backend-dev.sh start
curl -i http://127.0.0.1:7008/health
cd SrvRestAstroLS_v1/backend
uv run python -m scripts.ingestion_v2_kitzur_validate --run-id 492acd8d-06bd-42ac-a511-f3ec52f97bb3 --report-dir .../preflight-pg
uv run python -m scripts.book_qa_v2_hybrid_probe --run-id 492acd8d-06bd-42ac-a511-f3ec52f97bb3 --json '¿Qué relación hay entre hitbodedut y plegaria?'
uv run python -m scripts.book_qa_v2_kitzur_level2_acid_batch .../questions.json
```

- Búsquedas/consultas: 7 Book QA V2, 1 híbrida, 1 validador PostgreSQL y 57 verificaciones de página por variantes españolas.
- Candidatos Book QA revisados: 20; aceptados como apoyo: 4; descartados: 16 por recuperación genérica o ausencia de descomposición de la pregunta.
- Fuentes finales aceptadas: 33 pasajes de página; se muestran las citas representativas en las tablas.
- Motivos de descarte: página no esperada, snippet genérico, o incapacidad del clasificador para convertir una pregunta compuesta en conceptos individuales. No se descartó texto canónico por falta de modelo IA.

## Resultado final

| Pregunta | PASS/PARTIAL/FAIL | Páginas confirmadas | Faltantes |
| -------- | ----------------- | ------------------- | --------- |
| Teshuvá | PASS | 20–21, 29–33, 65–66, 204–205 | EHIéH no citado literalmente en la selección. |
| Pureza sexual | PASS | 17, 36, 81–82, 136–137, 140, 145 | Ninguno material. |
| Plegaria perfecta | PASS | 17–18, 25, 41, 60–61 | 292–293 y 331–332 sin cita final. |
| Hitbodedut | PASS | 65–66, 202–203, 237, 466 | 166–167 no aportaron variante en esta pasada. |
| Shabat | PASS | 159–160, 341, 343–344, 404, 461–462 | 328 sólo apoyo no citado. |
| Punto bueno | PASS | 407–409, 411 | 410 no añadió pasaje independiente. |
| Temor y ángeles | PASS | 419–424 | Ninguno material. |

## Límites

Este informe no reingesta, reindexa, modifica PostgreSQL, Milvus ni LiteLLM. La evidencia se verificó en el corpus candidato Kitzur y no autoriza promoción a producción. La síntesis editorial se apoya en fragmentos literales señalados; donde integra varios pasajes se etiqueta como paráfrasis cercana o temática.
