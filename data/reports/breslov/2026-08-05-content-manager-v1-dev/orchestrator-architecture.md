# Orchestrator architecture — functional closure

The PostgreSQL-durable boundary is preserved: canonical state graph, `FOR UPDATE SKIP LOCKED`, worker ownership, lease/heartbeat, compare-and-swap transitions, attempts, normalized manifests, active-job idempotency and tenant-scoped access.

`ConcretePageFirstPipeline` now provides the concrete worker dependency. `PsycopgWorkerStore` connects durable claims/transitions/results/failures; `PostgresMilvusPageFirstGateway` executes canonical extraction and isolated effects; `ManifestCleanupService` compensates partial attempts. HTTP requests only create/read jobs and never hold the pipeline open.

`content-worker-dev.sh` owns one DEV process by validated PID and loads the local default-off E2E settings. Its claim SQL filters `breslov_e2e`; it cannot claim primary jobs. Real E2E demonstrated claimed→extracting→normalizing→persisting_pages→building_chunks→embedding→indexing→validating_result→completed_with_warnings and `test_candidate`.
