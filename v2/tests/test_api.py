import json

import pytest
from fastapi.testclient import TestClient
from kyungdong_agent.data_hub import KyungdongRepository
from v2.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'test-access')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    repo = KyungdongRepository(tmp_path / 'test.db')
    with TestClient(create_app(repo), headers={'Authorization': 'Bearer test-access'}) as client:
        yield client


def test_workspace_and_read_only_tables(client):
    data = client.get('/api/workspace').json()
    assert len(data['questions']['데이터 기반']) == 10
    assert len(data['questions']['문서·규칙']) == 10
    assert data['meta']['demo_data'] is True
    assert data['meta']['ai_configured'] is False
    assert client.get('/api/tables/app_settings').status_code == 404
    assert client.get('/api/tables/materials?offset=-1').status_code == 422
    assert len(client.get('/api/tables/materials').json()['records']) <= 10


def test_project_isolation_and_explicit_project(client):
    for project in ['KGT-26001', 'KGT-26002']:
        response = client.post('/api/chat', json={'question': '경동아, 자재 LOT를 알려줘', 'project_id': project})
        assert response.status_code == 200
        data = response.json()
        assert data['mode'] == 'demo'
        rows = data['data_evidence'][0]['payload']['result']
        assert rows and all(row['project_id'] == project for row in rows)
    explicit = client.post('/api/chat', json={'question': '경동아, KGT-26002 자재 LOT', 'project_id': 'KGT-26001'}).json()
    assert explicit['project_id'] == 'KGT-26002'
    assert client.post('/api/chat', json={'question': '경동아, 현황', 'project_id': 'unknown'}).status_code == 404
    assert client.post('/api/chat', json={'question': '  '}).status_code == 422


def test_documents_and_evidence(client):
    docs = client.get('/api/documents?q=레이저').json()['documents']
    assert docs and any('레이저' in doc['content'] for doc in docs)
    data = client.post('/api/chat', json={'question': '경동아, FAT 체크리스트를 찾아줘'}).json()
    assert data['evidence'] and data['meta']['approval_status'] == '미승인 샘플'


def test_external_access_and_host_spoofing(client):
    assert client.get('/api/workspace', headers={'Authorization': ''}).status_code == 401
    assert client.get('/api/workspace', headers={'Authorization': '', 'Host': 'localhost'}).status_code == 401
    assert client.post('/api/realtime/tool', headers={'Authorization': ''}, json={'name': 'get_rules'}).status_code == 401


def test_ai_requires_server_key_and_tools_allowlist(client):
    assert client.post('/api/chat', json={'question': '경동아, 현황', 'mode': 'ai'}).status_code == 503
    assert client.post('/api/realtime/tool', json={'name': 'delete_records'}).status_code == 400
    result = client.post('/api/realtime/tool', json={'name': 'get_material_status', 'arguments': {'project_id': 'KGT-26001'}}).json()
    output = json.loads(result['output'])
    assert output['status'] == 'ok' and output['demo_data'] is True
    assert all(row['project_id'] == 'KGT-26001' for row in output['result'])


def test_local_access_requires_both_host_and_peer(tmp_path, monkeypatch):
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    app = create_app(KyungdongRepository(tmp_path / 'local.db'))
    with TestClient(app, base_url='http://localhost', client=('127.0.0.1', 5000)) as client:
        assert client.get('/api/workspace').status_code == 200
        assert client.get('/api/workspace', headers={'Host': 'external.example'}).status_code == 401


def test_realtime_session_uses_actual_manufacturing_tools(client, monkeypatch):
    import v2.api as module
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
    captured = {}
    class FakeHTTP:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return module.httpx.Response(200, text='v=0\r\n')
    monkeypatch.setattr(module.httpx, 'AsyncClient', FakeHTTP)
    response = client.post('/api/realtime/session?project_id=KGT-26001', content='v=0\r\n', headers={'Content-Type': 'application/sdp'})
    assert response.status_code == 200 and 'fake-key' not in response.text
    session = json.loads(captured['files']['session'][1])
    assert 'KGT-26001' in session['instructions']
    assert '조회시각은 근거 ID가 아닙니다' in session['instructions']
    assert '결과가 비어 있으면' in session['instructions']
    assert 'get_material_status' in {item['name'] for item in session['tools']}
    assert session['audio']['input']['turn_detection']['create_response'] is False
    assert session['audio']['input']['turn_detection']['interrupt_response'] is False
    assert client.post('/api/realtime/session', content=b'\xff', headers={'Content-Type': 'application/sdp'}).status_code == 400


def test_table_pagination_and_voice_provenance(client):
    first = client.get('/api/tables/materials').json()
    last = client.get(f"/api/tables/materials?offset={first['total']}").json()
    assert first['total'] >= len(first['records']) > 0
    assert last['records'] == []
    assert last['meta']['retrieved_at']
    response = client.post('/api/realtime/tool', json={
        'name': 'get_material_status', 'arguments': {'project_id': 'KGT-26001'}
    }).json()
    evidence = json.loads(response['output'])
    assert evidence['meta'] == response['meta']
    assert evidence['meta']['demo_data'] is True
    assert evidence['meta']['approval_status'] == '미승인 샘플'
    assert evidence['meta']['source']


def test_unaddressed_question_is_ignored_before_project_validation(client):
    result = client.post('/api/chat', json={'question': '자재 LOT를 알려줘', 'project_id': 'unknown'})
    assert result.status_code == 200
    body = result.json()
    assert body['ignored'] is True
    assert body['text'] == '' and body['evidence'] == [] and body['data_evidence'] == []


def test_wake_policy_is_exposed_and_recommended_questions_are_addressed(client):
    data = client.get('/api/workspace').json()
    assert data['meta']['wake']['agent_name'] == '경동아'
    assert all(q.startswith('경동아') for group in data['questions'].values() for q in group)
