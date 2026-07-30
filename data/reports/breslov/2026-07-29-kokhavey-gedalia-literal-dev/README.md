# Kokhavey Ohr / Gedalia nominal literal DEV gate

Fecha: 2026-07-29

Este reporte contiene únicamente identificadores técnicos y resultados
sanitizados. No contiene credenciales ni tokens.

## Baseline

El flujo real de `/research` devolvía `no_evidence` para `Gedalia of Linitz`
porque la fase de análisis confirmado ejecutaba siempre el pipeline avanzado.
Al invocar `simple_rag` directamente, PostgreSQL sí encontraba el literal,
mientras Milvus no ubicaba el chunk correcto en su top 30 para la consulta
corta.

## Autoridad canónica

- documento: `Kokhavey Ohr`
- archivo: `Kokhavey Ohr layout BH_PRINT-4.pdf`
- document ID: `c7c10741-c324-4916-93a7-61070863e3f9`
- SHA-256:
  `c38d41f92f73431e0c4905ce5a60f34de5933e224ea6e7fa6eb0594bb9c15761`
- estado: `ready`
- idioma: `en`
- scope: `breslov_primary`
- chunks/embeddings: `852 / 852`
- chunk principal: `91472546-4ffd-421c-9ec1-25d73d368352`
- página del chunk: `20–21`
- página local de la frase: `21`
- evidence ID: `ev-0f2b0ebedf5e0315`

El Markdown canónico contiene:

> Gedalia of Linitz and other great Rabbis, of blessed memory. They inspired
> Reb Noson to yearn to fulfill the Torah in practice, as they set an excellent
> example.

## Milvus

La colección `tebaai_breslov_chunks_v1` contiene el vector y la metadata
alineada del chunk principal, con dimensión 1536. Para la consulta corta el
chunk no apareció en top 30; para la frase ampliada apareció en rango 16. No se
recalcularon embeddings.

## Resultado corregido

La consulta exacta entrega:

- pipeline: `simple_rag`;
- idioma: `en`;
- shape: `short_proper_name`;
- estado: `complete`;
- match: `english_name_exact`;
- obra/archivo/página: `Kokhavey Ohr` / archivo esperado / página 21;
- chunk y evidence ID canónicos;
- respuesta grounded limitada al contexto de la mención;
- literal PostgreSQL y Milvus registrados por separado.

La variante `Gedalia of Linetz` recupera el mismo literal como aproximación,
pero queda `partial` y no afirma equivalencia editorial exacta.

## Restricciones respetadas

No se modificaron corpus, chunks, usuarios, PostgreSQL, Milvus, LiteLLM,
embeddings, migraciones, Nginx ni producción.
