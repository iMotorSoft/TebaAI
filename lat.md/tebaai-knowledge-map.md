# TebaAI Knowledge Map

This map provides a compact navigation tree for the canonical architecture and operational policies in `lat.md/`.

## Map

The tree groups stable concepts without replacing their canonical documents.

```mermaid
mindmap
  root((TebaAI))
    Platform
      Litestar backend
      Astro and Svelte frontend
      Generic content core
      Breslov first collection
    Configuration
      Typed settings
      globalVar facade
      Public global.js
      Secrets boundary
    Persistence
      PostgreSQL truth
      psycopg async
      SQL migrations
    Security
      Argon2id
      JWT access
      Opaque refresh
      Role guards
      Tenant context
    Library
      Knowledge scopes
      Documents
      Chunks
      Bibliographic metadata
      Page confidence
    Retrieval
      PostgreSQL FTS
      Milvus vectors
      LiteLLM embeddings
      AI gateway and aliases
      Hybrid merge
    Frontend
      Public configuration
      UI wrappers
      pnpm toolchain
    Validation
      Service preflight
      Playwright gate
      Root cause debugging
      LAT check
```

## Canonical References

Every branch resolves to one or more stable documents.

- platform and conventions: [[lat]];
- documentation: [[lat-documentation-policy]];
- configuration: [[global-configuration-facade-policy]];
- persistence: [[postgres-driver-policy]];
- security: [[authentication-security-policy]], [[tenant-context-authorization-policy]];
- frontend: [[frontend-implementation-policy]];
- AI gateway: [[ai-gateway-model-routing-policy]], [[embeddings-configuration-policy]];
- library and retrieval: [[knowledge-scope-contract]], [[library-retrieval-models-policy]], [[bibliographic-metadata-audit]], [[page-aware-metadata-mapping-audit]], [[page-metadata-enrichment]];
- primary research RAG decision: `docs/adr/ADR-006-simple-grounded-research-rag.md`;
- validation: [[service-preflight-methodology]], [[browser-mcp-validation-policy]], [[root-cause-debugging-policy]];
- diagrams: [[mermaid-diagram-policy]].

## Maintenance

The map changes only when a stable concept or canonical document is added, removed or renamed.

Daily evidence and temporary tasks belong in status or reports, not in this tree.
