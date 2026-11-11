import json
from types import SimpleNamespace
from kyungdong_agent.compound_graph import CompoundGraph
from kyungdong_agent.compound_questions import COMPOUND_QUESTIONS
from kyungdong_agent.data_hub import KyungdongRepository
from kyungdong_agent.factory_tools import KyungdongToolRegistry


def registry(tmp_path):
    return KyungdongToolRegistry(KyungdongRepository(tmp_path/'graph.db'))


def test_compound_retrieves_multiple_domains(tmp_path):
    answer=CompoundGraph(registry(tmp_path)).ask('자재 부족과 FAT 결과 및 검사 절차를 알려줘','KGT-26001')
    assert {'get_material_status','get_fat_quality'} <= {e['tool'] for e in answer['data_evidence']}
    assert answer['evidence']
    assert answer['engine']=='langgraph'
    assert all(e['arguments']['project_id']=='KGT-26001' for e in answer['data_evidence'])


def test_all_recommendations_have_multiple_queries(tmp_path):
    graph=CompoundGraph(registry(tmp_path))
    assert len(COMPOUND_QUESTIONS)==10
    for question in COMPOUND_QUESTIONS:
        assert len(graph.ask(question)['coverage'])>=2


def test_ai_second_plan_uses_results_and_cannot_escape_scope(tmp_path):
    class Fake:
        def __init__(self): self.responses=self; self.calls=0
        def with_options(self,**kwargs): return self
        def create(self,**kwargs):
            self.calls+=1
            if self.calls==1:
                output={'tasks':[{'request':'자재','tool':'get_material_status','arguments':{'project_id':'KGT-26002','issues_only':False}}]}
            elif self.calls==2:
                assert json.loads(kwargs['input'])['data']['previous_results']
                output={'tasks':[{'request':'품질','tool':'get_fat_quality','arguments':{}},{'request':'삭제','tool':'delete_records','arguments':{}}]}
            else: return SimpleNamespace(output_text='자재와 품질 근거를 확인했습니다.')
            return SimpleNamespace(output_text=json.dumps(output))
    fake=Fake()
    answer=CompoundGraph(registry(tmp_path),fake).ask('자재와 품질을 비교해줘','KGT-26001')
    assert fake.calls==4
    assert answer['partial']
    assert all(e['arguments']['project_id']=='KGT-26001' for e in answer['data_evidence'])
    assert len(answer['data_evidence'])==2


def test_failed_tool_preserves_success(tmp_path):
    reg=registry(tmp_path); original=reg.execute
    def execute(name,args):
        if name=='get_fat_quality': raise RuntimeError('db down')
        return original(name,args)
    reg.execute=execute
    answer=CompoundGraph(reg).ask('자재와 FAT','KGT-26001')
    assert answer['partial']
    assert {c['status'] for c in answer['coverage']}=={'found','failed'}


def test_explicit_comparison_scope(tmp_path):
    answer=CompoundGraph(registry(tmp_path)).ask('KGT-26001과 KGT-26002 자재 비교','KGT-26003')
    assert {e['arguments']['project_id'] for e in answer['data_evidence']}=={'KGT-26001','KGT-26002'}


def test_answer_audit_rejects_missing_quote_and_invalid_evidence(tmp_path):
    class Fake:
        def __init__(self): self.responses=self; self.calls=0
        def with_options(self,**kwargs): return self
        def create(self,**kwargs):
            self.calls+=1
            if self.calls==1: out={'tasks':[{'request':'자재 확인','tool':'get_material_status','arguments':{}}]}
            elif self.calls==2: out={'tasks':[]}
            elif self.calls==3: return SimpleNamespace(output_text='자재를 조회했습니다.')
            else:
                out={'checks':[{'request':'자재 확인','quote':'답변에 없는 내용','evidence_indices':[0],'status':'answered'}, {'request':'자재 상태','quote':'자재를 조회했습니다.','evidence_indices':[999],'status':'answered'}], 'voice_summary':'자재 기록을 조회했습니다. 자세한 내용은 화면에서 확인해 주세요.'}
            return SimpleNamespace(output_text=json.dumps(out))
    a=CompoundGraph(registry(tmp_path),Fake()).ask('자재 상태','KGT-26001')
    assert a['partial']
    assert all(c['status']=='unconfirmed' for c in a['request_coverage'])
    assert '추가 확인이 필요한 요청' in a['text']
    assert a['voice_summary']!='자재를 조회했습니다.'
