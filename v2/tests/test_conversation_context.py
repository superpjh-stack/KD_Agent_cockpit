from kyungdong_agent.conversation_context import resolve_scope, comparison_tables
from kyungdong_agent.compound_graph import CompoundGraph
from kyungdong_agent.factory_tools import KyungdongToolRegistry
from kyungdong_agent.data_hub import KyungdongRepository


def test_followup_scope_and_ambiguity():
    history=[{'role':'user','text':'KGT-26001 자재'}, {'role':'assistant','text':'KGT-26002'}]
    assert resolve_scope('그 프로젝트 납기도 알려줘',None,history)[0]==['KGT-26001']
    assert resolve_scope('그 프로젝트 납기도 알려줘','KGT-26003',history)[0]==['KGT-26003']
    assert resolve_scope('다른 프로젝트와 비교해줘',None,history)[2]
    assert resolve_scope('그 프로젝트 납기는?',None,[])[2]
    assert resolve_scope('그 프로젝트 KGT-26002',None,history)[0]==['KGT-26002']
    history=[{'role':'user','text':'KGT-26001 KGT-26002 비교'}]
    assert resolve_scope('그 프로젝트 납기는?',None,history)[2]
    assert len(resolve_scope('둘 다 납기를 알려줘',None,history)[0])==2


def test_followup_returns_same_project_and_new_session_does_not(tmp_path):
    graph=CompoundGraph(KyungdongToolRegistry(KyungdongRepository(tmp_path/'test.db')))
    result=graph.ask('그 프로젝트 납기와 자재를 비교해줘',history=[{'role':'user','text':'KGT-26001 자재'}])
    assert result['effective_projects']==['KGT-26001']
    assert result['comparison_tables']
    assert all(row[0]=='KGT-26001' for table in result['comparison_tables'] for row in table['rows'])
    fresh=graph.ask('그 프로젝트 납기는?')
    assert fresh['needs_clarification']
    assert not fresh['data_evidence']


def test_comparison_preserves_zero_units_and_unknown():
    rows=[{'tool':'get_material_status','status':'found','payload':{'result':[{'project_id':'KGT-26001','quantity':0,'unit':'EA'}]}}]
    table=comparison_tables(rows)[0]
    assert table['rows'][0][3:5]==['0','EA']
    assert table['rows'][0][1]=='미확인'
