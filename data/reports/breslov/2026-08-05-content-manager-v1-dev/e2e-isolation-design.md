# Content Manager write-E2E isolation

Write validation is disabled by default and requires development environment, an explicit E2E flag, exact `breslov_e2e` scope, exact `tebaai_content_manager_e2e_v1` collection and the configured generated-fixture SHA-256. The worker claim query itself filters the scope, so it cannot claim `breslov_primary` jobs.

The scope shares the authorized DEV tenant/project membership chain but carries `content_manager_e2e=true` and `primary_routing=false`. Milvus uses a separate collection with `attempt_key`, `job_id` and `attempt_number`; reconciliation and cleanup query only one attempt. The generated PDF is temporary and not versioned.

Primary routing, primary vector collection and existing documents are never selected by setup, worker, reconciliation or cleanup.
