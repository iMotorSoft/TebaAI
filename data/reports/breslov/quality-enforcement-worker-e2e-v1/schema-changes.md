# Schema changes

None. No migrations created or applied; no manual DDL/SQL patches.

Inspected canonical migrations `003_create_library_documents.sql`,
`014_create_library_ingestion_v2_tables.sql` and
`041_content_manager_orchestration_hardening.sql`, plus actual gateway writes.
`layout_notes`, extraction metadata, document metadata and job diagnostics
already provide JSONB storage. New tables are not justified by this inspection.
The DEV read-only probe confirms the four principal runtime tables exist.

A trusted certificate identity/ownership/approval contract must be defined
before choosing how to persist and transport its inputs. This run does not
claim that existing metadata alone supplies those inputs or enforces policy.
