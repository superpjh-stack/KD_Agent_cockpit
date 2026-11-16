import pytest
from fastapi.testclient import TestClient
from kyungdong_agent.data_hub import KyungdongRepository
from v2.api import create_app
from v2.knowledge_graph import build_graph

@pytest.fixture
def repo(tmp_path):
    return KyungdongRepository(tmp_path/'graph.db')

def test_scope_edges_and_passed_inspection(repo):
    graph=build_graph(repo,'KGT-26001')
    nodes={n['id']:n for n in graph['nodes']}
    assert any(n['label']=='IN-260901' and n['record']['result']=='합격' for n in nodes.values())
    assert all(n['record'].get('project_id','KGT-26001')=='KGT-26001' for n in nodes.values())
    for e in graph['edges']:
        assert e['source'] in nodes and e['target'] in nodes
        if e['label']=='입고검사':
            assert nodes[e['source']]['record']['material_lot']==nodes[e['target']]['record']['material_lot']==e['evidence']['value']
    assert graph==build_graph(repo,'KGT-26001')

def test_revision_zero_null_and_limit(repo):
    with repo._connect() as db:
        db.execute("INSERT INTO designs SELECT project_id,drawing_no,'D',bom_items,fem_status,change_no,change_status FROM designs WHERE project_id='KGT-26001'")
        db.execute("UPDATE operations SET actual_hours=0,plan_hours=NULL WHERE operation_id='OP-001'")
    graph=build_graph(repo,'KGT-26001')
    assert len([n for n in graph['nodes'] if n['kind']=='설계·변경'])==2
    row=next(n['record'] for n in graph['nodes'] if n['label']=='OP-001')
    assert row['actual_hours']==0 and row['plan_hours'] is None
    limited=build_graph(repo,'KGT-26001',limit=1)
    assert limited['truncated'] and limited['warnings']
    ids={n['id'] for n in limited['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in limited['edges'])

def test_graph_auth_validation_and_readonly(repo,monkeypatch):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','graph-test')
    before=repo.table_inventory()
    with TestClient(create_app(repo)) as c:
        assert c.get('/api/knowledge-graph?project_id=KGT-26001').status_code==401
        c.headers['Authorization']='Bearer graph-test'
        assert c.get('/api/knowledge-graph').status_code==422
        assert c.get('/api/knowledge-graph?project_id=missing').status_code==404
        assert c.get('/api/knowledge-graph',params={'project_id':"' OR 1=1 --"}).status_code==404
        r=c.get('/api/knowledge-graph?project_id=KGT-26002')
        assert r.status_code==200 and r.headers['cache-control']=='no-store'
        assert r.json()['meta']['demo_data'] is True
        assert c.get('/api/health').json()['version']=='4.0.0'
    assert before==repo.table_inventory()
