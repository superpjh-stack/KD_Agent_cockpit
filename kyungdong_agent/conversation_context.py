"""Resolve follow-up project references without sharing state across sessions."""
import re


def resolve_scope(question, selected, history):
    explicit=list(dict.fromkeys(re.findall(r'KGT-\d{5}',question.upper())))
    if explicit: return explicit, '질문에 지정한 프로젝트', None
    followup=any(word in question for word in ['그 프로젝트','해당 프로젝트','그것','그건','거기는','그러면','그럼','이어서','다른 것','다른 프로젝트','두 프로젝트','둘 다','둘을'])
    if not followup: return [selected], '선택 프로젝트' if selected else '전체 프로젝트', None
    previous=[]
    for turn in reversed(history or []):
        if turn.get('role')!='user': continue
        ids=list(dict.fromkeys(re.findall(r'KGT-\d{5}',turn.get('text','').upper())))
        if ids: previous=ids;break
    if any(word in question for word in ['다른 것','다른 프로젝트']):
        return [selected], '대상 확인 필요', '어느 프로젝트와 비교할까요? 비교할 프로젝트 번호를 알려주세요.'
    if selected: return [selected], '선택 프로젝트', None
    if len(previous)==1 or (len(previous)>1 and any(w in question for w in ['두 프로젝트','둘 다','둘을'])):
        return previous, '이전 질문의 프로젝트', None
    return [None], '대상 확인 필요', '어느 프로젝트를 말씀하시나요? 프로젝트 번호를 알려주세요.'


def comparison_tables(results):
    """Build tables directly from returned records, preserving units and source IDs."""
    fields={
      'get_lead_time_status':[('project_id','프로젝트'),('status','상태'),('due_date','납기'),('progress_pct','진행률 (%)'),('plan_hours','계획 공수 (h)'),('actual_hours','실제 공수 (h)'),('delayed_operations','지연 공정 수')],
      'get_quote_analysis':[('project_id','프로젝트'),('predicted_cost_mkr','예상 원가 (백만원)'),('margin_pct','예상 이익률 (%)'),('predicted_lead_days','예상 기간 (일)'),('model_status','예측 상태')],
      'get_material_status':[('project_id','프로젝트'),('material_lot','자재 LOT'),('stock_status','재고 상태'),('quantity','수량'),('unit','단위'),('mtc_status','MTC')],
      'get_fat_quality':[('project_id','프로젝트'),('test_id','시험 ID'),('test_item','시험 항목'),('measured_value','측정값'),('unit','단위'),('result','판정'),('resolution','조치')],
    }
    tables=[]
    for tool, columns in fields.items():
        rows=[];seen=set()
        for result in results:
            if result['tool']!=tool or result['status']!='found': continue
            values=result['payload'].get('result',[])
            if not isinstance(values,list): continue
            for row in values:
                if not isinstance(row,dict):continue
                cells=[str(row.get(key)) if row.get(key) is not None else '미확인' for key,_ in columns]
                key=tuple(cells)
                if key not in seen:seen.add(key);rows.append(cells)
        if rows:tables.append({'tool':tool,'columns':[label for _,label in columns],'rows':rows})
    return tables
