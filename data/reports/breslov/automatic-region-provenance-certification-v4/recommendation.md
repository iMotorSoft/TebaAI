# Recommendation

V4 passes its sealed holdout (safety 0 unsafe, body 87/117, notes 72/100,
cross 7/7), fixes the V3 real-permutation failure and keeps all five V1 unsafe
zones unresolved.

- `READY_FOR_C_REINGEST = NO`.
- `CERTIFICATES_READY_FOR_WORKER_INTEGRATION = NO` until an independent
  holdout and a worker integration phase approve it.
- Do not reseal or reopen the V4 holdout to tune V4.
- Next step: run V4 through the worker integration design on a fresh,
  independent holdout, then decide reingest.

Commit = NO; push = NO; branch changes = NO; services managed = NO.
PostgreSQL writes = NO; Milvus writes = NO; C reingest = NO; production
changes = NO; OCR = NO; orthographic search changes = NO.
