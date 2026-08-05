# Rollback plan

No migration was applied and no runtime data was written in this continuation.

Code rollback is commit-scoped: revert the Content Manager hardening commit. Migration 041 must not be removed after application; a forward migration would be required. Before any future write E2E, cleanup must use exact manifest IDs and an isolated Milvus collection. Never delete by title, filename or broad timestamp and never drop a shared collection.
