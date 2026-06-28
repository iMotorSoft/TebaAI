# Historial tecnico TebaAI hasta 2026-06-28

Este documento congela los cierres tecnicos anteriores a la consolidacion del tablero vigente. Git conserva el detalle completo de cada cambio y validacion.

## Bootstrap y stack

TebaAI adopto Litestar, Astro 7, Svelte 5, Tailwind CSS 4, DaisyUI 5, PostgreSQL 18, Milvus 2.6 y LiteLLM como base tecnica.

- backend en `127.0.0.1:7008`;
- frontend en `127.0.0.1:3008`;
- entrypoint `backend/ls_iMotorSoft_Srv01.py`;
- Playwright + Chromium como gate E2E;
- Mermaid como fuente de diagramas.

## Configuracion y PostgreSQL

Se implementaron settings tipados, fachada `globalVar.py`, pool async, transacciones, health, readiness y migraciones SQL idempotentes.

- `core/config.py` concentra variables `TEBAAI_*`;
- `globalVar.py` no crea recursos vivos;
- `global.js` contiene configuracion publica;
- PostgreSQL usa `psycopg 3 async` sin ORM;
- migraciones `001` a `007` cubren infraestructura, auth, biblioteca, embeddings, FTS y metadata bibliografica.

## Autenticacion y frontend

Se implementaron usuarios, sesiones, login, refresh, logout, roles y administracion basica.

- Argon2id para passwords;
- JWT de acceso;
- refresh opaco con hash, rotacion y deteccion de reutilizacion;
- roles `admin`, `editor`, `viewer`;
- UI de login y administracion de usuarios;
- E2E autenticado originalmente uso un fallback versionado, retirado en la consolidacion documental.

## Biblioteca e ingestion

Se construyo una biblioteca generica con la primera coleccion Breslov como datos, no como logica de plataforma.

- ingesta Markdown, texto y PDF;
- extraccion con `pymupdf4llm`;
- entidades de coleccion, documento, texto y referencia;
- chunking persistido en PostgreSQL;
- tres PDF procesados en la ejecucion inicial;
- 1.991 vectores historicos y 1.990 chunks reportados por auditorias posteriores.

## Retrieval

Se implementaron retrieval textual, vectorial e hibrido manteniendo PostgreSQL como fuente de verdad.

- FTS PostgreSQL con `unaccent`, `pg_trgm`, configuraciones `spanish` y `simple`;
- Milvus con COSINE y HNSW;
- embeddings `text-embedding-3-small` mediante LiteLLM;
- merge hibrido y deduplicacion por `chunk_id`;
- endpoint autenticado `POST /library/search`;
- UI de busqueda bibliografica.

## Auditoria bibliografica

Las auditorias separaron metadata verificada de inferencias heuristicas para evitar inventar paginas o capitulos.

- 284 de 1.990 chunks recibieron paginas de alta confianza;
- paginas fisicas del PDF, no numeracion impresa;
- contenido, embeddings y vectores no fueron alterados por el enriquecimiento;
- resultado de evaluacion registrado: 26/30 PASS.

## Deudas heredadas al cierre

Las deudas vigentes fueron trasladadas al tablero compacto y no deben gestionarse desde este historial.

- reconciliacion chunks/vectores;
- cookies `httpOnly` y refresh automatico;
- paginacion de usuarios;
- OCR y metadata de confianza media;
- limite plataforma TebaAI / vertical Breslov;
- futuro RAG generativo sujeto a ADR.
