# Decisión de implementación parcial — no aprobación de runtime

## Contrato de publicación

`publishable_region = quality_status == ACCEPTED AND provenance_status == CERTIFIED`

Además el certificado debe estar ligado a la misma fuente SHA-256, página física, region_id, bbox y rango forward que su unidad. Un certificado ausente, duplicado o discordante no autoriza texto. No se aceptan cadenas por parecer limpias. Estados SOURCE_PDF_ERROR / PLATFORM_EXTRACTION_ERROR / UNRESOLVED se conservan como diagnóstico, con publication_status=QUARANTINED.

## Implementado

`modules/library/region_publication.py` consume los tipos existentes `CertifiedPage` / `Ownership` / `RegionCertificate`, sin depender de una versión V5 concreta. Filtra las unidades antes de concatenar. Entrega:

- canonical_markdown sólo aceptado;
- evidence_units separadas por región, para chunking independiente sin overlap a través de un hueco;
- FULL / PARTIAL / UNUSABLE;
- inventario sin texto rechazado: estado original, razón, hash del candidato y referencia a fuente/página/región/bbox;
- aviso explícito de limitación textual (ninguna traducción o reconstrucción).

Los errores locales de certificado no suprimen unidades independientes aceptadas. Ownership duplicado/inventario contradictorio se rechaza explícitamente; ownership solapado no permite publicar texto ambiguo.

## No implementado

No se ha cambiado el worker, su extractor, el gateway, la retención del PDF, el esquema ni la API. `source_reference` es un locator, NO una garantía de almacenamiento durable ni una URL autorizada. La API actual no recibe aún estos metadatos.

No activar este consumidor dejando el resto del pipeline igual: el gateway aún chunkea páginas enteras y finalize borra el temporal. Tampoco usar canonical_markdown concatenado como única entrada a chunking: eso podría unir regiones a ambos lados de un hueco.

## Integración restante (requisito de este mismo gate)

1. Transportar inventario y unidades certificadas en ExtractedPage; escoger una representación forward única, sin mapear certificados V5 sobre rangos de page_markdown por búsqueda inversa.
2. Persistir canónico exclusivamente aceptado y metadata de cuarentena sin texto dudoso; chunkear cada evidence_unit por separado con region_id trazable.
3. Mantener archivo PDF durable, vinculado al documento y tenant, antes de eliminar el temporal. Incluir retención/cleanup idempotente del recurso; exponer referencia visual autorizada y advertencia de página parcial.
4. Evitar rechazo global cuando una página tiene regiones aceptadas. Una página UNUSABLE no debe impedir conservar páginas útiles del documento.
5. Ejecutar worker real DEV aislado, LiteLLM real, Milvus real, retrieval/citas reales, replay y cleanup por IDs/manifest.

Estas son tareas pendientes de implementación, no una imposibilidad arquitectónica ni una nueva exigencia de OCR, holdout independiente o perfección de V5. No se cambia certificación ni evaluación para obtener positivos.

## Dependencias

El nuevo consumidor importa sólo módulos ya versionados en HEAD. El probe real usa el V5 local preexistente y su cadena existente V4 → V3 → V2 → V1 + provenance + annotation_preseal_validation. No se versionó esa cadena ni se la hizo dependencia de runtime. No se modificó trabajo preexistente.
