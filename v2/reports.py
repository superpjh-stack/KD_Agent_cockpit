"""Project manufacturing reports with immutable source snapshots."""
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from uuid import uuid4
from typing import Literal
import json,re,unicodedata
from xml.sax.saxutils import escape
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field,ConfigDict

TITLES={'projects':'프로젝트 현황 보고서','materials':'자재·입고검사 보고서','operations':'공정 공수 보고서','fat':'FAT 품질 보고서','quotes':'견적·원가 예측 보고서'}
class ReportInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    kind:Literal['projects','materials','operations','fat','quotes']
    project_id:str|None=Field(None,max_length=80)

def initialize(repo):
    with repo._connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS v3_report_exports (report_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)')

def snapshot(repo,body):
    if body.project_id and not repo.projects(body.project_id): raise HTTPException(404,'프로젝트를 찾을 수 없습니다.')
    args=(body.project_id,) if body.project_id else ()
    where=' WHERE project_id=?' if args else ''
    notes=['경동글로벌텍 검증용 DB · 가상·미승인 샘플입니다. 실제 운영 실적 또는 승인 결과가 아닙니다.', '생성 시점에 조회한 스냅샷입니다. 빈 값은 미입력으로 표시합니다.']
    if body.kind=='projects':
        source=repo.projects(body.project_id)
        keys=['project_id','customer','equipment_type','due_date','status','progress_pct']
        columns=['프로젝트','고객','설비 유형','납기','상태','진행률 %']
    elif body.kind=='materials':
        source=repo._query('SELECT m.*, i.inspection_id, i.inspection_date, i.result AS inspection_result, i.note AS inspection_note FROM materials m LEFT JOIN incoming_inspections i ON m.material_lot=i.material_lot'+(' WHERE m.project_id=?' if args else '')+' ORDER BY m.material_lot,i.inspection_date',args)
        keys=['project_id','material_lot','specification','quantity','unit','mtc_status','stock_status','inspection_result']
        columns=['프로젝트','자재 LOT','규격','수량','단위','MTC','재고 상태','검사 결과']
        notes.append('검사 이력이 여러 개면 자재 LOT가 반복됩니다. 반복 행의 재고를 합산하지 않습니다. 상세 검사일과 메모는 Excel 원본 시트에서 확인하세요.')
    elif body.kind=='operations':
        source=repo._query('SELECT * FROM operations'+where+' ORDER BY project_id,operation_id',args)
        keys=['project_id','process','status','plan_hours','actual_hours','hours_difference','due_date']
        columns=['프로젝트','공정','상태','계획 h','실제/누적 h','차이 h','납기']
        for r in source:r['hours_difference']=None if r['plan_hours'] is None or r['actual_hours'] is None else round(r['actual_hours']-r['plan_hours'],4)
        notes.append('차이 = 실제/누적 공수 − 계획 공수. 진행 중 공수는 확정 실적이 아니며 차이만으로 효율 또는 초과 원인을 판정하지 않습니다.')
    elif body.kind=='fat':
        source=repo.fat_quality(body.project_id)
        keys=['project_id','test_item','measured_value','unit','limit_text','result','resolution']
        columns=['프로젝트','시험 항목','측정값','단위','기준','결과','조치 계획']
        notes.append('등록된 판정을 그대로 표시합니다. 보고서 생성은 FAT 합격 승인이나 출하 승인이 아닙니다.')
    else:
        source=repo.quote_analysis(body.project_id)
        keys=['project_id','order_amount_mkr','predicted_cost_mkr','margin_pct','predicted_lead_days','model_status']
        columns=['프로젝트','수주금액 백만원','예측원가 백만원','예상이익률 %','예측납기 일','모델 상태']
        notes.append('모든 예측 지표는 등록된 모델 추정값입니다. 확정 원가·실현 이익·보장 납기가 아닙니다.')
    if not source:raise HTTPException(404,'조건에 맞는 원본 기록이 없습니다.')
    return {'kind':body.kind,'title':TITLES[body.kind],'project_id':body.project_id,'business_date':None,'columns':columns,'rows':[[r.get(k) for k in keys] for r in source],'source_rows':source,'source':'경동글로벌텍 DB · '+(body.project_id or '전체 프로젝트'),'as_of':'원본 기준일 미등록','notes':notes,'created_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'report_id':uuid4().hex}

def create(repo,body):
    data=snapshot(repo,body);initialize(repo)
    with repo._connect() as db:db.execute('INSERT INTO v3_report_exports VALUES (?,?)',(data['report_id'],json.dumps(data,ensure_ascii=False)))
    return {k:v for k,v in data.items() if k!='source_rows'}

def export_xlsx(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = '보고서'
    ws.append(['경동글로벌텍 · '+data['title']]); ws.append(['기준일', data['business_date'] or data['as_of'], '생성 시각', data['created_at']])
    ws.append(['출처', data['source']]); ws.append([' / '.join(data['notes'])]); ws.append(data['columns'])
    for row in data['rows']: ws.append(row)
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str): cell.data_type = 's'
            cell.font = Font(name='맑은 고딕', size=10)
            cell.alignment = Alignment(vertical='center',wrap_text=True)
    for cell in ws[5]:
        cell.fill = PatternFill('solid', fgColor='173F4B'); cell.font = Font(color='FFFFFF',bold=True)
    width = max(len(data['columns']),4)
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=width)
    ws.merge_cells(start_row=4,start_column=1,end_row=4,end_column=width)
    ws.row_dimensions[1].height = 32; ws.row_dimensions[4].height = 65
    for i in range(1,width+1): ws.column_dimensions[get_column_letter(i)].width = 30 if i<=2 else 20
    ws.freeze_panes='A6'; ws.auto_filter.ref=f'A5:{get_column_letter(len(data["columns"]))}{ws.max_row}'
    ws.print_title_rows='1:5'; ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A4; ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0
    ws.print_options.horizontalCentered=True
    source = wb.create_sheet('원본 스냅샷')
    keys = list(dict.fromkeys(k for row in data['source_rows'] for k in row))
    source.append(keys)
    for row in data['source_rows']: source.append([row.get(k) for k in keys])
    for row in source:
        for cell in row:
            if isinstance(cell.value,str): cell.data_type='s'
    source.freeze_panes='A2'
    buffer=BytesIO(); wb.save(buffer); return buffer.getvalue()

def export_pdf(data):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
    pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
    style=ParagraphStyle('ko',fontName='HYSMyeongJo-Medium',fontSize=9,leading=14,wordWrap='CJK')
    p=lambda value: Paragraph(escape(unicodedata.normalize('NFC','미입력' if value is None else str(value))),style)
    buffer=BytesIO(); doc=SimpleDocTemplate(buffer,pagesize=landscape(A4),rightMargin=30,leftMargin=30,topMargin=25,bottomMargin=25)
    story=[p('경동글로벌텍 · '+data['title']),p('기준일: '+str(data['business_date'] or data['as_of'])+' / 생성: '+data['created_at']),p('출처: '+str(data['source'])),*[p(n) for n in data['notes']],Spacer(1,12)]
    table=LongTable([[p(c) for c in data['columns']]]+[[p(c) for c in r] for r in data['rows']],colWidths=[doc.width/len(data['columns'])]*len(data['columns']),repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),'#E6EFF0'),('GRID',(0,0),(-1,-1),.3,'#BCCFD2'),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(table)
    def footer(canvas, doc):
        canvas.setFont('HYSMyeongJo-Medium',8); canvas.drawString(30,12,f"{data['report_id']} · {doc.page}")
    doc.build(story,onFirstPage=footer,onLaterPages=footer); return buffer.getvalue()

def chat_request(question,project_id):
    if not re.search(r'보고서|실적표|점검표',question):return None
    if re.search(r'일일|일별|오늘|어제|최근|지난|이번|부터|까지|\d{4}[-./]|\d+월',question):raise ValueError('현재 보고서는 등록 기록 스냅샷입니다. 일별 실적·기간 필터는 지원하지 않습니다. 프로젝트별 현황 보고서를 요청해 주세요.')
    matches=re.findall(r'KGT-\d+',question,re.I)
    if len(set(matches))>1:raise ValueError('프로젝트별 보고서는 한 프로젝트씩 요청하세요.')
    if matches:
        if project_id and project_id.upper()!=matches[0].upper():raise ValueError('선택 프로젝트와 질문의 프로젝트가 다릅니다.')
        project_id=matches[0].upper()
    kind='fat' if re.search(r'FAT|품질',question,re.I) else 'materials' if re.search(r'자재|입고|MTC',question,re.I) else 'operations' if re.search(r'공정|공수',question) else 'quotes' if re.search(r'견적|원가|이익',question) else 'projects' if '프로젝트' in question or '현황' in question else None
    if not kind:return None
    return ReportInput(kind=kind,project_id=project_id)

def install(app,get_repo):
    @app.post('/api/reports')
    def generate(body:ReportInput):return create(get_repo(),body)
    @app.get('/api/reports/{report_id}/{extension}')
    def download(report_id:str,extension:str):
        if not re.fullmatch(r'[a-f0-9]{32}',report_id) or extension not in ('xlsx','pdf'):raise HTTPException(404,'파일을 찾을 수 없습니다.')
        repo=get_repo();initialize(repo)
        rows=repo._query('SELECT snapshot FROM v3_report_exports WHERE report_id=?',(report_id,))
        if not rows:raise HTTPException(404,'보고서를 찾을 수 없습니다.')
        data=json.loads(rows[0]['snapshot'])
        content=export_xlsx(data) if extension=='xlsx' else export_pdf(data)
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if extension=='xlsx' else 'application/pdf',headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="kgt-{report_id}.{extension}"'})
