"""Offline fixture applicability metrics; never used by production.

Author intent is not permission to publish. Stage observations are region-ID sets,
not aggregate counts (a duplicate/replacement cannot hide a missing neighbor).
"""


def worker_metrics(boundary, stages, visual_regions):
    accepted = {rid for rid, (quality, provenance) in boundary.items()
                if quality == 'ACCEPTED' and provenance == 'CERTIFIED'}
    rejected = set(boundary) - accepted
    survived = set.intersection(*(set(ids) for ids in stages.values()))
    searchable = set.union(*(set(ids) for ids in stages.values()))
    return {
        'GOOD_NEIGHBOR_LOSS': len(accepted - survived),
        'BAD_REGION_LEAK': len(searchable - accepted),
        'SOURCE_PRESERVATION_FAIL': len(rejected - set(visual_regions)),
    }


def certifier_recall_miss(author_good, boundary):
    """Intent-relative mismatch only; does NOT judge actual source quality."""
    return sum(boundary[rid][0] == 'UNRESOLVED' for rid in author_good)


def partial_page_searchable(boundary, stages):
    accepted = {rid for rid, verdict in boundary.items()
                if verdict == ('ACCEPTED', 'CERTIFIED')}
    survived = set.intersection(*(set(ids) for ids in stages.values()))
    return bool(accepted & survived) and bool(set(boundary) - accepted)
