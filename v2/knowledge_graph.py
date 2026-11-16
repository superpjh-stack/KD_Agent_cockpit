"""Read-only, evidence-backed graph projection of manufacturing records."""
import hashlib
import json

SPECS = [
    ('designs', '설계·변경', 'drawing_no', '설계 기록'),
    ('materials', '자재 LOT', 'material_lot', '사용 자재'),
    ('operations', '공정', 'operation_id', '제작 공정'),
    ('fat_tests', 'FAT', 'test_id', 'FAT 검사'),
    ('purchase_orders', '구매', 'po_no', '구매 기록'),
    ('equipment_readings', '설비 측정', 'reading_id', '설비 측정'),
    ('claims', '클레임', 'claim_id', '클레임 기록'),
]


def build_graph(repo, project_id, limit=200):
    projects = repo.projects(project_id)
    if not projects:
        raise ValueError('프로젝트를 찾지 못했습니다.')
    nodes, edges, warnings = [], [], []

    def node(kind, label, table, record):
        # Full-record digest also distinguishes drawing revisions without a primary key.
        digest = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:24]
        nid = f'{table}:{digest}'
        if not any(n['id'] == nid for n in nodes):
            nodes.append({'id': nid, 'kind': kind, 'label': str(label), 'table': table, 'record': record})
        return nid

    def edge(source, target, label, field, value):
        edges.append({'id': f'e{len(edges)}', 'source': source, 'target': target, 'label': label,
                      'evidence': {'field': field, 'value': value}})

    project = projects[0]
    root = node('프로젝트', project_id, 'projects', project)
    if project.get('customer'):
        customer = node('고객', project['customer'], 'projects.customer',
                        {'project_id': project_id, 'customer': project['customer']})
        edge(customer, root, '고객 프로젝트', 'projects.customer', project['customer'])
    lots = {}
    for table, kind, key, relation in SPECS:
        rows = repo._query(f'SELECT * FROM {table} WHERE project_id=? ORDER BY {key} LIMIT ?', (project_id, limit + 1))
        if len(rows) > limit:
            warnings.append(f'{kind}: {limit}건까지만 표시합니다.')
        for row in rows[:limit]:
            label = row[key]
            if table == 'designs':
                label = f"{label} · Rev {row.get('revision') or '미확인'}"
            nid = node(kind, label, table, row)
            edge(root, nid, relation, f'{table}.project_id', project_id)
            if table == 'materials':
                lots[row['material_lot']] = nid
    # Join by the actual LOT key, including passed inspections (not just issues).
    inspections = repo._query('SELECT i.* FROM incoming_inspections i JOIN materials m ON i.material_lot=m.material_lot WHERE m.project_id=? ORDER BY i.inspection_id LIMIT ?', (project_id, limit + 1))
    if len(inspections) > limit:
        warnings.append(f'입고검사: {limit}건까지만 표시합니다.')
    for row in inspections[:limit]:
        if row['material_lot'] not in lots:
            warnings.append('표시 제한으로 자재가 없는 입고검사는 생략했습니다.')
            continue
        nid = node('입고검사', row['inspection_id'], 'incoming_inspections', row)
        edge(lots[row['material_lot']], nid, '입고검사', 'incoming_inspections.material_lot', row['material_lot'])
    return {'project_id': project_id, 'nodes': nodes, 'edges': edges,
            'warnings': list(dict.fromkeys(warnings)), 'truncated': bool(warnings)}
