from io import BytesIO
import pytest
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from kyungdong_agent.data_hub import KyungdongRepository
from v2.api import create_app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','test-access')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    repo=KyungdongRepository(tmp_path/'test.db')
    app=create_app(repo)
    with TestClient(app,headers={'Authorization':'Bearer test-access'}) as c:
        c.repo=repo
        yield c

@pytest.mark.parametrize('kind',['projects','materials','operations','fat','quotes'])
def test_reports_snapshot_exports_scope(client,kind):
    r=client.post('/api/reports',json={'kind':kind,'project_id':'KGT-26001'})
    assert r.status_code==200,r.text
    report=r.json();assert all(row[0]=='KGT-26001' for row in report['rows'])
    assert 'source_rows' not in report
    rid=report['report_id']
    x=client.get(f'/api/reports/{rid}/xlsx');assert x.status_code==200
    wb=load_workbook(BytesIO(x.content));assert wb.active['A6'].value=='KGT-26001'
    assert wb['원본 스냅샷'].max_row>1
    assert client.get(f'/api/reports/{rid}/pdf').content.startswith(b'%PDF')
    assert client.get(f'/api/reports/{rid}/pdf',headers={'Authorization':''}).status_code==401
    if kind=='projects':
        with client.repo._connect() as db:db.execute("UPDATE projects SET customer='changed'")
        wb2=load_workbook(BytesIO(client.get(f'/api/reports/{rid}/xlsx').content))
        assert wb2.active['B6'].value==report['rows'][0][1]

def test_chat_filters_and_formula_protection(client):
    r=client.post('/api/chat',json={'question':'KGT-26002 공정 공수 보고서 만들어줘'})
    assert r.status_code==200 and r.json()['report']['project_id']=='KGT-26002'
    for q in ['오늘 공정 보고서','2026-09-01 프로젝트 보고서','KGT-26001 KGT-26002 현황 보고서']:
        assert client.post('/api/chat',json={'question':q}).status_code==422
    assert client.post('/api/reports',json={'kind':'projects','business_date':'2026-09-01'}).status_code==422
    assert client.post('/api/reports',json={'kind':'projects','project_id':'missing'}).status_code==404
    with client.repo._connect() as db:db.execute("UPDATE projects SET customer='=1+1'")
    r=client.post('/api/reports',json={'kind':'projects'}).json()
    wb=load_workbook(BytesIO(client.get(f"/api/reports/{r['report_id']}/xlsx").content))
    assert wb.active['B6'].data_type=='s'

@pytest.mark.parametrize('mode',['ideas','detective','journey','briefing'])
def test_studio_modes(client,mode):
    r=client.post('/api/studio',json={'mode':mode,'project_id':'KGT-26001'})
    assert r.status_code==200,r.text
    result=r.json();assert len(result['pipeline'])==3
    valid={f['id'] for f in result['evidence']}
    for f in result['evidence']:
        assert all(row.get('project_id')=='KGT-26001' for row in f['records'])
    for card in result['cards']:
        assert set(card['evidence_ids'])<=valid
        if card['kind']=='creative':assert not card['evidence_ids']
    assert '샘플' in result['source_notice']

def test_studio_missing_and_no_key(client):
    assert client.post('/api/studio',json={'mode':'detective'}).status_code==422
    assert client.post('/api/studio',json={'mode':'ideas','use_ai':True}).status_code==503
