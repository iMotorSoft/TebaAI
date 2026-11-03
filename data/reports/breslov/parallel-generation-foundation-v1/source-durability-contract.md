# Source durability — unresolved, no metadata repair

SOURCE_DURABILITY_RESOLVED = NO

Current C: source_path=NULL, source_uri=NULL. External original exists, 4,550,267 bytes, 284 pages, SHA256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`. The deterministic document-owned source file under configured Content Manager storage is absent in both new inventories. Downloads availability is not durability.

Existing implementation to reuse: `modules/library/durable_source.py`: deterministic `sources/<physical-document-id>/original.pdf`, hash validation, temporary copy + file fsync + atomic replace + directory fsync. `source_reference` uses authenticated document-specific route. This gate did not call preserve_source, copy a PDF, repair metadata or invoke extraction.

Missing proof: durable storage persistence/backup and restore/retention policy for the effective storage root, generation retention fencing (remove_source is currently callable by cleanup), authenticated current-C source access, and binding of per-generation source/provenance seal. fsync proves a local atomic write, not retention or backup. No new storage subsystem or Download URL fallback was invented.

Future repair, only after storage/lifecycle proof: hash approved original, preserve_source to the existing configured generation-owned location, verify bytes/pages/hash, transactionally bind source metadata with audit, verify authorized viewer and C content fingerprints. Keep this separate from content ingestion. A metadata repair is not justified merely to turn this field green.

[Before source](source-before.json), [after source](source-after.json), [protected inventory](after-c-inventory.json). No durable location is claimed; source metadata remains unchanged.
