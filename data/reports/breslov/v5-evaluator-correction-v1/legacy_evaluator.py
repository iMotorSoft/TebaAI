def page_source(inventory, number):
    return next((page for page in inventory if page['page'] == number))

def flat_line_ids(page):
    result = set()
    for box in page['boxes']:
        for line in box['lines']:
            for identifier in line['ids']:
                result.add(tuple(identifier))
    return result

def separator_y(page):
    for box in page['boxes']:
        for line in box['lines']:
            if line['text'].replace('�', '').strip() in ('Notas y Fuentes', 'Notas y Fuentes:', 'Notes and Sources'):
                return line['bbox'][1]
    return None

def source_audit(pages, rows, inventory, canonical, *, part):
    by_key = {(row['pdf_page'], row['region_id']): row for row in rows}
    by_page = {page.provenance.pdf_page: page for page in pages}
    metrics = {'unsafe_false_certifications': 0, 'unsafe_false_provenance_certifications': 0, 'false_body_certifications': 0, 'false_cross_page_links': 0, 'false_editorial_completions': 0, 'false_identity_proven': 0, 'inconsistent_identity_state': 0}
    violations = []
    linked_pairs = []
    for row in rows:
        page = page_source(inventory, row['pdf_page'])
        ids = flat_line_ids(page)
        owned = all((tuple(item) in ids for item in row['source_line_ids']))
        certified = row['provenance_status'] == 'CERTIFIED'
        accepted = row['quality_status'] == 'ACCEPTED'
        if certified and (not owned):
            metrics['unsafe_false_provenance_certifications'] += 1
            violations.append({'kind': 'false_provenance', 'row': row})
        if accepted and (not owned):
            metrics['unsafe_false_certifications'] += 1
            violations.append({'kind': 'false_certification', 'row': row})
        if accepted and row['zone_type'] == 'MAIN_BODY':
            limit = separator_y(page)
            if limit is not None:
                boxes = {tuple(line['ids'][0]): line['bbox'][1] for box in page['boxes'] for line in box['lines'] if len(line['ids']) == 1}
                ys = [boxes[tuple(item)] for item in row['source_line_ids'] if tuple(item) in boxes]
                if ys and max(ys) > limit:
                    metrics['false_body_certifications'] += 1
                    violations.append({'kind': 'false_body', 'row': row})
        if row['linked_region_ids']:
            target = by_key.get((row['pdf_page'] + 1, row['linked_region_ids'][0]))
            target_page = canonical.get(row['pdf_page'] + 1, [])
            terminal_units = [unit for unit in canonical.get(row['pdf_page'], []) if unit.get('note_number') is not None]
            leading = target_page[0] if target_page else None
            terminal = terminal_units[-1] if terminal_units else None
            source_ok = bool(target and target['editorial_unit_id'] == row['editorial_unit_id'] and (target['note_number'] == row['note_number']) and (target['identity_state'] == 'IDENTITY_PROVEN') and (row['identity_state'] == 'IDENTITY_PROVEN') and terminal and (terminal.get('note_number') == row['note_number']) and (terminal.get('end_reason') == 'PAGE_BOUNDARY') and leading and (leading.get('note_number') == row['note_number']) and leading.get('parts') and (leading['parts'][0]['text'].strip()[:3].isdigit() is False))
            linked_pairs.append({'from': row['pdf_page'], 'to': row['pdf_page'] + 1, 'note': row['note_number'], 'target_region': row['linked_region_ids'][0], 'source_ok': source_ok})
            if not source_ok:
                metrics['false_cross_page_links'] += 1
                violations.append({'kind': 'false_link', 'row': row})
        completion = row['continuation_state'] == 'COMPLETE_LOCAL' or row['continuation_status'] == 'CROSS_PAGE_COMPLETE'
        if completion and row['zone_type'] == 'note':
            next_units = canonical.get(row['pdf_page'] + 1, [])
            if next_units and next_units[0].get('continuation_of_page') == row['pdf_page']:
                metrics['false_editorial_completions'] += 1
                violations.append({'kind': 'false_completion', 'row': row})
        identity_proven = row['identity_state'] == 'IDENTITY_PROVEN'
        if identity_proven and (not row['linked_region_ids']):
            metrics['false_identity_proven'] += 1
            metrics['inconsistent_identity_state'] += 1
            violations.append({'kind': 'identity_without_link', 'row': row})
        if row['linked_region_ids'] and (not identity_proven):
            metrics['inconsistent_identity_state'] += 1
            violations.append({'kind': 'link_without_identity', 'row': row})
        if row['identity_state'] == 'CANDIDATE_CONTINUATION' and row['continuation_state'] == 'COMPLETE_LOCAL':
            metrics['inconsistent_identity_state'] += 1
            violations.append({'kind': 'candidate_complete', 'row': row})
    return (metrics, violations, linked_pairs)
