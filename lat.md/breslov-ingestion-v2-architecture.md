# Breslov Ingestion V2 — Architecture

Estado: `draft`
Ultima actualizacion: 2026-07-09
Autor: TebaAI agent

---

## 1. Problema

El modelo de ingesta actual (V1) convierte PDF → texto → chunks → embeddings. Esto funciona para búsqueda FTS y vectorial, pero es insuficiente para investigación bibliográfica estructurada:

| Problema | Impacto | Evidencia |
|---|---|---|
| Sin tabla de páginas | No se puede responder "¿qué hay en la página X?" | Book QA acid test: page_ok=1/10 |
| Sin tabla de secciones | No se puede navegar por estructura del libro | Preguntas sobre "Señor del Campo", "Canción del Futuro" sin contexto estructural |
| Sin tabla de conceptos | Las variantes se resuelven por heurística, no por datos | Q4 detectó "literalmente" en vez de "hitbodedut" |
| Sin tabla de fuentes/referencias | Las citas bíblicas y rabínicas no tienen entidad propia | No se puede responder "¿dónde cita el Zohar?" |
| Sin tabla de relaciones internas | Las conexiones entre conceptos se infieren en runtime | Relation QA no puede restringir a un libro específico |
| Sin wiki de documento | No hay metadata de alto nivel sobre qué temas cubre un libro | Book QA acid test global: 11.9/20 WARN |

## 2. Objetivos

La Ingesta V2 debe habilitar:

- **Book QA**: preguntas restringidas a un libro específico con respuesta textual exacta
- **Relation QA**: relaciones conceptuales con scoping documental opcional
- **Cross-Book QA**: comparación de conceptos entre libros
- **Concept QA**: localización de todas las menciones de un concepto en el corpus
- **Synapse Search**: búsqueda que cruza conceptos, fuentes, secciones y referencias
- **Citas auditables**: cada afirmación resuelve a libro/página/sección/chunk exactos

## 3. Entidades V2

Nuevas tablas PostgreSQL para páginas, secciones, conceptos, fuentes, relaciones y wiki.

### 3.1 DocumentV2

Extiende library_documents existente sin crear tabla nueva.

```
library_documents  (existente, sin cambios)
  └─ Se agregan vistas/virtuales para compatibilidad V2
```

### 3.2 PageV2 — tabla nueva

Cada página física del documento tiene una fila.

```sql
CREATE TABLE library_pages_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    page_number INTEGER NOT NULL,
    text TEXT,
    char_start INTEGER,
    char_end INTEGER,
    char_count INTEGER,
    extraction_method TEXT,
    layout_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (document_id, page_number)
);
```

### 3.3 SectionV2 — tabla nueva

Cada sección/capítulo/subsección del documento.

```sql
CREATE TABLE library_sections_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    parent_section_id UUID REFERENCES library_sections_v2(id),
    title TEXT NOT NULL,
    section_type TEXT,
    page_start INTEGER,
    page_end INTEGER,
    order_index INTEGER NOT NULL,
    path TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (document_id, path)
);
```

### 3.4 ChunkV2 (extiende library_document_chunks existente)

La tabla actual `library_document_chunks` ya tiene la mayoría de campos necesarios: `page_start`, `page_end`, `section`, `section_title`, `node_path`, `block_type`, `evidence_role`. Se agrega:

- `section_id UUID REFERENCES library_sections_v2(id)` (nullable, backfilled)

No se crea tabla nueva; se extiende la existente con FK opcional a sections_v2.

### 3.5 ConceptMentionV2 — tabla nueva

Cada mención de un concepto en un chunk.

```sql
CREATE TABLE library_concept_mentions_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES library_document_chunks(id),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    label TEXT NOT NULL,
    normalized_label TEXT NOT NULL,
    variants TEXT[],
    language TEXT,
    span_start INTEGER,
    span_end INTEGER,
    confidence REAL DEFAULT 0.8,
    concept_type TEXT,
    extraction_method TEXT DEFAULT 'auto',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_concept_mentions_normalized ON library_concept_mentions_v2(normalized_label);
CREATE INDEX idx_concept_mentions_chunk ON library_concept_mentions_v2(chunk_id);
```

### 3.6 SourceReferenceV2 — tabla nueva

Cada referencia a fuente externa (bíblica, rabínica, talmúdica, etc.).

```sql
CREATE TABLE library_source_references_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES library_document_chunks(id),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    reference_text TEXT NOT NULL,
    source_type TEXT NOT NULL,
    normalized_ref TEXT,
    citation_target TEXT,
    evidence_type TEXT,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_source_refs_type ON library_source_references_v2(source_type);
CREATE INDEX idx_source_refs_normalized ON library_source_references_v2(normalized_ref);
```

### 3.7 InternalRelationV2 — tabla nueva

Relaciones conceptuales entre conceptos dentro del mismo documento.

```sql
CREATE TABLE library_internal_relations_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    concept_a TEXT NOT NULL,
    concept_b TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence_type TEXT,
    page_start INTEGER,
    page_end INTEGER,
    chunk_ids UUID[],
    snippet TEXT,
    confidence REAL DEFAULT 0.5,
    extraction_method TEXT DEFAULT 'auto',
    editorial_status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_internal_relations_concepts ON library_internal_relations_v2(concept_a, concept_b);
```

### 3.8 DocumentWikiV2 — tabla nueva

Resumen editorial generado para cada documento.

```sql
CREATE TABLE library_document_wiki_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL UNIQUE REFERENCES library_documents(id),
    overview TEXT,
    structure_summary TEXT,
    main_topics TEXT[],
    key_concepts TEXT[],
    source_map JSONB,
    internal_relations_summary JSONB,
    questions_it_can_answer TEXT[],
    warnings TEXT[],
    generated_at TIMESTAMPTZ,
    review_status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.9 IngestionRunV2 — tabla nueva

Registro de ejecuciones de ingesta.

```sql
CREATE TABLE library_ingestion_runs_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    source_sha256 TEXT,
    pipeline_version TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    metrics_json JSONB,
    warnings_json JSONB
);
```

## 4. Estados editoriales

Ciclo de vida editorial para los datos de ingesta V2.

```text
draft               → extracción automática inicial
auto_extracted      → pipeline V2 completo ejecutado
test_candidate      → listo para revisión editorial
reviewed            → editor humano aprobó
ready               → corpus estable interno
deprecated          → reemplazado por versión más nueva
```

## 5. Evidence types (extiende los 22 existentes)

Se mantienen los 22 tipos actuales y se agregan:

```text
explicit_relation   → relación A-B declarada textualmente
implicit_relation   → relación A-B inferida por contexto
structural_relation → relación A-B por estructura del libro (misma sección)
```

## 6. Cómo soporta rutas de chat

Cada ruta de consulta usa una combinación de tablas V2 para dar contexto estructural.

| Ruta | Mecanismo V2 |
|---|---|
| **source_lookup** | SourceReferenceV2 → busca por normalized_ref → devuelve chunk + página |
| **book_qa** | Relation QA con `document_id` opcional + PageV2 + SectionV2 para scoping |
| **relation_qa** | Relation QA existente + ConceptMentionV2 para expansión conceptual |
| **concept_qa** | ConceptMentionV2 → busca por normalized_label → agrupa por documento/página |
| **cross_book_qa** | ConceptMentionV2 multi-documento + InternalRelationV2 |
| **synapse_search** | Híbrido: FTS + ConceptMention + SourceReference + InternalRelation |
| **clarify** | DocumentWikiV2 → overview + main_topics para contexto |

## 7. Compatibilidad con sistema actual

```
SISTEMA ACTUAL (V1)          SISTEMA V2
─────────────────            ────────────
library_documents            library_documents (sin cambios)
library_document_texts       library_document_texts (sin cambios)
library_document_chunks      library_document_chunks + section_id FK opcional
library_chunk_embeddings     library_chunk_embeddings (sin cambios)
knowledge_scopes             knowledge_scopes (sin cambios)
                             
                             library_pages_v2 (nueva)
                             library_sections_v2 (nueva)
                             library_concept_mentions_v2 (nueva)
                             library_source_references_v2 (nueva)
                             library_internal_relations_v2 (nueva)
                             library_document_wiki_v2 (nueva)
                             library_ingestion_runs_v2 (nueva)
```

**Principio**: V2 no modifica tablas V1. Solo agrega:
- Tablas nuevas (prefijo `_v2`)
- FK opcional `section_id` en `library_document_chunks`
- Vistas de compatibilidad si es necesario

## 8. Piloto: El Jardín de las Almas

Primer documento para la ingesta V2 completa:

1. Extraer páginas a `library_pages_v2`
2. Extraer secciones a `library_sections_v2`
3. Extraer conceptos a `library_concept_mentions_v2`
4. Extraer fuentes a `library_source_references_v2`
5. Extraer relaciones a `library_internal_relations_v2`
6. Generar wiki a `library_document_wiki_v2`
7. Vincular chunks existentes a `section_id`
8. Registrar ejecución en `library_ingestion_runs_v2`
9. Validar con las 10 preguntas del Book QA acid test

## 9. Gap analysis del Book QA acid test

Ver `data/reports/breslov/2026-07-09-jardin-almas-book-qa-acid-test/`

| ID | Falla | Causa | Qué necesita Ingesta V2 | Ruta futura |
|---|---|---|---|---|
| Q1 | Página incorrecta | No hay tabla de páginas para buscar por página 36 | PageV2 permite "dame página 36 de documento X" | book_qa |
| Q2 | Libro incorrecto | Relation QA no acepta scoping por documento | `document_id` opcional en request | book_qa |
| Q3 | Página incorrecta | Página 280 no localizable sin PageV2 | PageV2 para scoping por página | book_qa |
| Q4 | Página incorrecta | Concepto "Daat" buscado sin scoping | ConceptMentionV2 para localizar menciones | concept_qa |
| Q5 | Página incorrecta | "Señor del Campo" sin sección conocida | SectionV2 para estructura | book_qa |
| Q6 | Libro incorrecto | "talón del Otro Lado" no matchea | ConceptMentionV2 para variantes | concept_qa |
| Q7 | Fragmento parcial | Canción del Futuro encontrada, faltan matices | InternalRelationV2 para relaciones entre conceptos | cross_book_qa |
| Q8 | Libro incorrecto | "tefilá bibejinat din" en otro libro aparece primero | SourceReferenceV2 para referencias exactas | source_lookup |
| Q9 | Libro incorrecto | Vecino/agregado no localizado en este libro | SectionV2 + ConceptMention para contexto | book_qa |
| Q10 | Página incorrecta | Pregunta multi-página sin soporte | InternalRelationV2 + ConceptMention multi-página | synapse_search |

## 10. Próximos pasos

Secuencia de implementación recomendada para la ingesta V2.

1. Aprobar diseño → crear migraciones SQL
2. Implementar script de ingesta V2 piloto para El Jardín de las Almas
3. Ejecutar piloto en `breslov_test` (no productivo)
4. Validar con Book QA acid test
5. Si PASS → promover a documentación canónica
6. Crear endpoint `/library/book-qa` con scoping documental
7. Extender a los otros 7 libros del corpus
