# Fixture applicability / responsibility contract

The prior `TEBAAI_BRESLOV_REGION_QUARANTINE_WORKER_E2E_V1_FAIL` remains valid.
Its frozen PDF expectations A/C/D were not met. This new gate does not edit,
relax, rerun or retrospectively pass that gate.

Pipeline: fixture/source → certifier → publication policy → worker.
Human intent is not an upstream certificate and cannot authorize publication.

| Event | Responsible layer |
|---|---|
| Raw region ends UNRESOLVED | certifier |
| ACCEPTED+CERTIFIED produces no chunk | worker/publication |
| UNRESOLVED produces a chunk | worker/publication safety defect |
| ACCEPTED+CERTIFIED produces chunk/vector/retrieval | expected behavior |
| Quarantined region retains visual source | worker/source preservation |
| UNRESOLVED absent from search | expected behavior |

## Type 1: policy / worker contract

Declared valid internal classifications, no real certifier. The actual production
publication boundary, worker orchestrator, pipeline and region chunk builder run.
I/O adapters are in-memory; they record region IDs at canonical/chunk/embedding
input/embedding/vector stages. Mixed A accepted, B quarantined, C accepted must
publish A/C only. All-good publishes 3/3; all-bad publishes zero (not neighbor
loss). ACCEPTED without CERTIFIED remains excluded. The existing durable-source
regressions use temporary local files, not a new storage service.

No claim of fresh Milvus/retrieval/citation integration from those doubles.
Those product stages are supported by prior frozen actual E2E evidence.

## Type 2: full pipeline

Worker expectations derive from actual frozen certifier outputs, not intended
GOOD labels. A/C/D have 1/2/1 author-intended GOOD regions; all four are
UNRESOLVED, never ACCEPTED+CERTIFIED. They must not become searchable.
Record these four as intent-relative CERTIFIER_RECALL_MISS, not worker loss.
Whether the source deserved certification and why V5 declined are out of scope.

GOOD_NEIGHBOR_LOSS counts distinct ACCEPTED+CERTIFIED boundary regions lost at
any required downstream stage. It is not a difference of aggregate counts.
BAD_REGION_LEAK counts distinct nonpublishable IDs at any searchable stage.
Controlled downstream loss, bad publication and missing-source observations
must trigger the corresponding metric; production is never mutated.

PARTIAL_PAGE_SEARCHABLE requires a same-page accepted certified survivor and
another nonpublishable region. It does not require accepting every intended
GOOD region. Prior real original p54–56 each meet this definition. Their
3 accepted regions survive chunks → embeddings → vectors → retrieval → canonical
citations. Visual access was verified before authorized cleanup; this is frozen
historical evidence, not a claim that cleaned fixtures still exist in DEV.

A real worker defect stops this gate without a production fix. Production,
V4/V5, source truth, prior results and preexisting worktree must remain unchanged.
Full C reingest is not authorized by this contract.
