# Cutover CAS — proposed, NOT implemented or executed

`switch_active_generation(logical_id, expected_generation_id, target_generation_id, operation_key, expected_epoch)` must run in one psycopg async transaction. Authorize tenant/scope, lock logical lifecycle row and target ownership, compare current pointer/epoch **before** mutation. Mismatch -> STALE_ACTIVE_GENERATION; no status/pointer/audit change. Use guarded UPDATE as well as row lock. Exactly one of OLD->A / OLD->B may commit.

Target must exist, belong to logical owner, be READY and not quarantined/deleting/deleted; required source identity, durable reference, completed build provenance/resource seal must exist. Do not require content-quality comparisons that belong to future C Safety V2. The accepted quality policy still applies to any generation produced by existing ingestion.

Atomically update pointer/epoch and audit. Former active becomes retained inactive by pointer derivation; never delete resources or issue vector writes here. A lost-response retry consults the recorded operation/request digest; it must not blindly switch again. A distinct stale operation cannot receive false success just because target happens to be current.

The same lifecycle lock must fence cleanup/publication/retry, including across external deletes. All readers pin/validate epochs; two independent publish calls are not a cutover. No PG transaction/concurrency proof or callable primitive was delivered in this attempt.
