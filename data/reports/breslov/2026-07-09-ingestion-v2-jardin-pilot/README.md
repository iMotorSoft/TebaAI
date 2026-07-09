# Ingestion V2 Pilot — El Jardín de las Almas

Probe read-only para planificar la ingesta V2.

## Documento

| Métrica | Valor |
|---|---|
| Document ID | `76f2adbc-b79a-4432-9ea5-521a337a5502` |
| Título | El Jardín de las Almas |
| Status | `ready` |
| Chunks en top-50 probe | 11 |
| Páginas detectadas | 9 (rango: 45-82) |
| Evidence types | biblical_citation (100%) |
| Sections | 0 (no hay metadata de sección en chunks) |
| Section candidates | 8 (detectados por heurística de snippets) |
| Conceptos detectados (de 23 buscados) | 8 |
| Fuentes referenciadas | Zohar, Torá, Talmud, Breslov, Ketuvim |
| Page mapping | Sin page_start/page_end en chunks (none block_type) |
| Block types | 11/11 sin block_type asignado |

## Hallazgos

1. El libro está en el corpus productivo (`ready`) con chunks básicos.
2. No hay page mapping ni block_type en los chunks actuales.
3. El libro fue ingestado con el pipeline simple, no layout-aware.
4. Se detectaron 8 secciones candidatas por heurística de headers markdown.
5. Hay conceptos clave presentes (alma, tzadik, plegaria, bitul).
6. Hay fuentes referenciadas (Zohar, Torá, Talmud) pero sin tabla de referencias.

## Próximo paso

Ejecutar ingesta V2 completa sobre `breslov_test` antes de promover a productivo.
