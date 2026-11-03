"""Standalone source evaluator; no certifier imports or corpus I/O.

Contract: ../v5-evaluator-correction-v1/evaluator-semantics-contract.md
"""
EVALUATOR_VERSION = 'v5-evaluator-correction-v1'


def page_source(inventory, number):
    return next(page for page in inventory if page['page'] == number)


def flat_line_ids(page):
    return {tuple(identifier) for box in page['boxes'] for line in box['lines']
            for identifier in line['ids']}


def separator_y(page):
    for box in page['boxes']:
        for line in box['lines']:
            if line['text'].replace('\ufffd', '').strip() in (
                    'Notas y Fuentes', 'Notas y Fuentes:', 'Notes and Sources'):
                return line['bbox'][1]
    return None


def canonical_link_relation(a, b):
    """Unordered, page-qualified endpoints: reciprocal claims score once."""
    return tuple(sorted((a, b)))


def canonical_completion_state(row):
    """Relation status CROSS_PAGE_COMPLETE never implies local completion."""
    return row['continuation_state'] == 'COMPLETE_LOCAL'


def _matching_rows(rows, page, unit):
    ids = {tuple(i) for part in unit.get('parts', []) for i in part.get('ids', [])}
    candidates = [r for r in rows if r['pdf_page'] == page
                  and r['note_number'] == unit.get('note_number')]
    if ids:
        return [r for r in candidates if {tuple(i) for i in r['source_line_ids']} == ids]
    # Historical synthetic audit had no IDs. Only unambiguous fallback is allowed.
    return candidates if len(candidates) == 1 else []


def _expected_relations(rows, canonical):
    expected = set()
    outgoing = set()
    for page, units in canonical.items():
        for leading in units:
            previous = leading.get('continuation_of_page')
            if previous is None or page != previous + 1:
                continue
            terminals = [u for u in canonical.get(previous, []) if u.get('note_number') is not None]
            if not terminals:
                continue
            terminal = terminals[-1]
            if (terminal.get('note_number') != leading.get('note_number')
                    or terminal.get('end_reason') != 'PAGE_BOUNDARY'):
                continue
            sources = _matching_rows(rows, previous, terminal)
            targets = _matching_rows(rows, page, leading)
            outgoing.update((r['pdf_page'], r['region_id']) for r in sources)
            if len(sources) == len(targets) == 1:
                expected.add(canonical_link_relation(
                    (previous, sources[0]['region_id']), (page, targets[0]['region_id'])))
    return expected, outgoing


def _proof_compatible(row):
    return not any(p.get('passed') is False for p in row.get('identity_proof', []))


def source_audit(pages, rows, inventory, canonical, *, part):
    """Audit stored rows against source truth; never invoke the candidate.

    pages/part retained for compatibility. Missing expected rows are represented
    by the gate's existing positive-pair missed_links counter; this audit tracks
    missing relations whose two source endpoints are present.
    """
    by_key = {(r['pdf_page'], r['region_id']): r for r in rows}
    if len(by_key) != len(rows):
        raise ValueError('Duplicate page-qualified region IDs')
    metrics = {name: 0 for name in (
        'unsafe_false_certifications', 'unsafe_false_provenance_certifications',
        'false_body_certifications', 'false_cross_page_links',
        'false_editorial_completions', 'false_identity_proven',
        'inconsistent_identity_state', 'unsafe_false_identity_proven',
        'missed_true_links', 'missing_reciprocal_links', 'valid_cross_page_relations')}
    violations = []
    expected, outgoing = _expected_relations(rows, canonical)
    claims = {}
    for row in rows:
        key = (row['pdf_page'], row['region_id'])
        for target_id in set(row['linked_region_ids']):
            # Resolve actual endpoint before normalization; never assume +1 for backrefs.
            adjacent = [(p, target_id) for p in (row['pdf_page'] - 1, row['pdf_page'] + 1)
                        if (p, target_id) in by_key]
            preferred = row['pdf_page'] + (-1 if row['continuation_state'] == 'CONTINUED_FROM_PREVIOUS' else 1)
            target = (preferred, target_id)
            if len(adjacent) == 1:
                target = adjacent[0]
            relation = canonical_link_relation(key, target)
            claims.setdefault(relation, set()).add((key, target))
    valid = set()
    unsafe = set()
    linked_pairs = []
    for relation, directions in sorted(claims.items()):
        a, b = relation
        left, right = by_key.get(a), by_key.get(b)
        senders = [by_key[source] for source, _ in directions]
        ok = bool(relation in expected and left and right
                  and left['editorial_unit_id']
                  and left['editorial_unit_id'] == right['editorial_unit_id']
                  and left['note_number'] == right['note_number']
                  and (not left['linked_region_ids'] or b[1] in left['linked_region_ids'])
                  and (not right['linked_region_ids'] or a[1] in right['linked_region_ids'])
                  and all(r['identity_state'] == 'IDENTITY_PROVEN' and _proof_compatible(r)
                          for r in senders))
        linked_pairs.append({'from': a[0], 'to': b[0],
                             'from_region': a[1], 'target_region': b[1],
                             'note': left['note_number'] if left else None,
                             'source_ok': ok, 'representations': len(directions)})
        if ok:
            valid.add(relation)
            if len(directions) != 2:
                metrics['missing_reciprocal_links'] += 1
                violations.append(dict(kind='missing_reciprocal', relation=relation))
        else:
            metrics['false_cross_page_links'] += 1
            violations.append(dict(kind='false_link', relation=relation))
            unsafe.update(k for k in relation if k in by_key
                          and by_key[k]['identity_state'] == 'IDENTITY_PROVEN')
    metrics['unsafe_false_identity_proven'] = len(unsafe)
    metrics['missed_true_links'] = len(expected - valid)
    metrics['valid_cross_page_relations'] = len(valid)
    for row in rows:
        page = page_source(inventory, row['pdf_page'])
        ids = flat_line_ids(page)
        owned = all(tuple(item) in ids for item in row['source_line_ids'])
        certified = row['provenance_status'] == 'CERTIFIED'
        accepted = row['quality_status'] == 'ACCEPTED'
        if certified and not owned:
            metrics['unsafe_false_provenance_certifications'] += 1
            violations.append({'kind': 'false_provenance', 'row': row})
        if accepted and not owned:
            metrics['unsafe_false_certifications'] += 1
            violations.append({'kind': 'false_certification', 'row': row})
        if accepted and row['zone_type'] == 'MAIN_BODY':
            limit = separator_y(page)
            if limit is not None:
                boxes = {tuple(line['ids'][0]): line['bbox'][1]
                         for box in page['boxes'] for line in box['lines'] if len(line['ids']) == 1}
                ys = [boxes[tuple(item)] for item in row['source_line_ids'] if tuple(item) in boxes]
                if ys and max(ys) > limit:
                    metrics['false_body_certifications'] += 1
                    violations.append({'kind': 'false_body', 'row': row})
        if (canonical_completion_state(row) and row['zone_type'] == 'note'
                and (row['pdf_page'], row['region_id']) in outgoing):
            metrics['false_editorial_completions'] += 1
            violations.append({'kind': 'false_completion', 'row': row})
        identity_proven = row['identity_state'] == 'IDENTITY_PROVEN'
        if identity_proven and not row['linked_region_ids']:
            metrics['false_identity_proven'] += 1
            metrics['inconsistent_identity_state'] += 1
            violations.append({'kind': 'identity_without_link', 'row': row})
        if row['linked_region_ids'] and not identity_proven:
            metrics['inconsistent_identity_state'] += 1
            violations.append({'kind': 'link_without_identity', 'row': row})
        if row['identity_state'] == 'CANDIDATE_CONTINUATION' and row['continuation_state'] == 'COMPLETE_LOCAL':
            metrics['inconsistent_identity_state'] += 1
            violations.append({'kind': 'candidate_complete', 'row': row})
    return metrics, violations, linked_pairs
