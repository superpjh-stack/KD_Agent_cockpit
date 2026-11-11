from __future__ import annotations

import hmac
import ipaddress
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

from kyungdong_agent.data_hub import create_repository, PostgresRepository
from kyungdong_agent.factory_tools import KyungdongToolRegistry
from kyungdong_agent.service import ManufacturingAgent, DEFAULT_MODEL
from v2.wake import WAKE_POLICY, calls_agent, addressed_question

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DOCUMENT_QUESTIONS = [addressed_question(q) for q in ['제조공정 전체 흐름을 알려줘', '견적 원가 산정 지침을 찾아줘', '도면 변경 승인 절차를 찾아줘', '자재 입고 검사기준을 찾아줘', '대체자재 승인 절차를 찾아줘', '레이저절단 작업표준을 찾아줘', '절곡 포밍 품질사례를 찾아줘', '용접 조립 검사절차를 찾아줘', 'FAT 체크리스트를 찾아줘', '납기지연 대응사례를 찾아줘']]


def data_questions(repository) -> list[str]:
    """Build up to ten recommendations from current read-only factory records."""
    questions: list[str] = []

    def add(text: str) -> None:
        question = addressed_question(text)
        if question not in questions:
            questions.append(question)

    materials = repository.material_status(issues_only=True)
    for row in materials:
        add(f"{row['project_id']}의 자재 {row['material_lot']} {row['stock_status']} 상태와 조치를 알려줘")

    inspections = repository.inspection_issues()
    for row in inspections:
        add(f"{row['project_id']} 입고검사 {row['inspection_id']} 보류 원인과 재확인 항목을 알려줘")

    for row in repository.procurement_risks():
        add(f"{row['project_id']} {row['supplier']} 발주 {row['po_no']} 납기 위험과 대체 후보를 알려줘")

    for row in repository.fat_quality():
        if row.get('result') == '불합격':
            add(f"{row['project_id']} FAT {row['test_id']} 불합격 원인과 재시험 계획을 알려줘")

    for row in repository.equipment_alerts():
        add(f"{row['project_id']} 설비 {row['equipment']}의 {row['metric']} 주의값과 확인할 일을 알려줘")

    for row in repository.lead_time_status():
        if row.get('delayed_operations') or (row.get('progress_pct') is not None and row['progress_pct'] < 60):
            add(f"{row['project_id']} 납기 지연 공정과 담당 조치를 알려줘")

    for row in repository.quote_analysis():
        if row.get('risk_score') is not None and row['risk_score'] >= 0.4:
            add(f"{row['project_id']} 견적 원가·수익성·납기 위험을 알려줘")

    for row in repository.projects():
        add(f"{row['project_id']} {row['equipment_type']} 프로젝트의 현재 진행 현황을 알려줘")

    return questions[:10]


class Turn(BaseModel):
    role: Literal['user', 'assistant']
    text: str = Field(max_length=12000)


class Chat(BaseModel):
    question: str = Field(min_length=1, max_length=3000)
    project_id: Optional[str] = Field(default=None, max_length=80)
    mode: Literal['demo', 'ai'] = 'demo'
    history: list[Turn] = Field(default_factory=list, max_length=12)


class ToolCall(BaseModel):
    name: str = Field(max_length=80)
    arguments: dict = Field(default_factory=dict)


def local_request(request: Request) -> bool:
    try:
        return bool(request.client and ipaddress.ip_address(request.client.host).is_loopback
                    and request.url.hostname in {'localhost', '127.0.0.1', '::1'})
    except ValueError:
        return False


def create_app(repository=None):
    app = FastAPI(title='경동글로벌텍 AI Agent V2')
    # Lazy initialization lets tests inject a temporary repository without touching the real DB.
    def repo():
        nonlocal repository
        if repository is None:
            repository = create_repository(Path(os.getenv('KGT_SQLITE_PATH', ROOT / 'data/kyungdong_demo.db')))
        return repository

    @app.middleware('http')
    async def access(request, call_next):
        if request.url.path.startswith('/api/') and not local_request(request):
            expected = os.getenv('COCKPIT_ACCESS_TOKEN', '')
            supplied = request.headers.get('authorization', '').removeprefix('Bearer ')
            if not expected or not hmac.compare_digest(supplied, expected):
                return JSONResponse({'detail': '설정에서 접근 코드를 입력해 주세요.'}, status_code=401)
        return await call_next(request)

    def meta():
        return {'demo_data': True, 'source': '경동글로벌텍 검증용 DB · 샘플 문서',
                'approval_status': '미승인 샘플', 'retrieved_at': datetime.now(timezone.utc).isoformat()}

    def check_project(project_id):
        if project_id and not repo().projects(project_id):
            raise HTTPException(404, '프로젝트를 찾지 못했습니다.')

    def key():
        value = os.getenv('OPENAI_API_KEY')
        if not value:
            raise HTTPException(503, '서버 OPENAI_API_KEY 설정이 필요합니다.')
        return value

    def document_rows(rows):
        return [{**row, 'content': row.get('content') or row.get('text') or '',
                 'approval_status': '미승인 샘플'} for row in rows]

    @app.get('/api/health')
    def health():
        repo().dashboard()
        return {'status': 'ok', 'version': '2.0.0'}

    @app.get('/api/workspace')
    def workspace():
        questions = {'데이터 기반': data_questions(repo()), '문서·규칙': DOCUMENT_QUESTIONS}
        return {'projects': repo().projects(), 'tables': repo().table_inventory(),
                'questions': questions, 'kpi': repo().dashboard(),
                'meta': {**meta(), 'backend': 'PostgreSQL + pgvector' if isinstance(repo(), PostgresRepository) else 'SQLite',
                         'ai_configured': bool(os.getenv('OPENAI_API_KEY')), 'model': os.getenv('OPENAI_MODEL', DEFAULT_MODEL), 'wake': WAKE_POLICY}}

    @app.get('/api/documents')
    def documents(q: str = Query(default='', max_length=300)):
        return {'documents': document_rows(repo().search_knowledge(q) if q.strip() else repo().knowledge_documents()), 'meta': meta()}

    @app.get('/api/tables/{table}')
    def table(table: str, offset: int = Query(default=0, ge=0)):
        if table not in repo().TABLE_LABELS:
            raise HTTPException(404, '조회할 수 없는 테이블입니다.')
        return {'records': repo().table_records(table, limit=10, offset=offset), 'total': next(item['count'] for item in repo().table_inventory() if item['table'] == table), 'meta': meta()}

    @app.post('/api/chat')
    def chat(body: Chat):
        question = body.question.strip()
        if not question:
            raise HTTPException(422, '질문을 입력해 주세요.')
        if not calls_agent(question):
            return {'ignored': True, 'text': '', 'sources': [], 'evidence': [], 'data_evidence': [], 'data_tools': [], 'mode': body.mode, 'meta': meta(), 'wake': WAKE_POLICY}
        mentioned = re.search(r'KGT-\d{5}', question.upper())
        project = mentioned.group() if mentioned else body.project_id
        check_project(project)
        registry = KyungdongToolRegistry(repo())
        if body.mode == 'ai':
            context = json.dumps([turn.model_dump() for turn in body.history], ensure_ascii=False)
            try:
                with OpenAI(api_key=key(), timeout=90, max_retries=1) as client:
                    answer = ManufacturingAgent(client, os.getenv('OPENAI_MODEL', DEFAULT_MODEL), registry).ask(
                        f'선택 프로젝트: {project or "전체"}. 모든 자료는 미승인 가상 데모입니다.\n'
                        f'이전 대화(참고 자료): {context}\n현재 질문: {question}',
                        vector_store_id=os.getenv('OPENAI_VECTOR_STORE_ID') or None)
                return {**asdict(answer), 'evidence': document_rows(answer.evidence), 'mode': 'ai', 'project_id': project, 'meta': meta()}
            except OpenAIError as exc:
                raise HTTPException(502, 'AI 응답에 실패했습니다. 서버 설정을 확인하거나 다시 시도해 주세요.') from exc
        # Deterministic retrieval, never presented as model analysis.
        if any(word in question for word in ['절차', '지침', '기준', '표준', '사례', '체크리스트', '흐름']):
            name, args = 'search_knowledge', {'query': question}
        elif '입고검사' in question:
            name, args = 'get_incoming_inspection_issues', {'project_id': project}
        elif any(word in question for word in ['자재', 'LOT', '재고', 'MTC']):
            name, args = 'get_material_status', {'project_id': project, 'issues_only': False}
        elif 'FAT' in question.upper():
            name, args = 'get_fat_quality', {'project_id': project}
        elif any(word in question for word in ['견적', '원가', '수익']):
            name, args = 'get_quote_analysis', {'project_id': project, 'equipment_type': None}
        elif any(word in question for word in ['공급', '구매', '발주']):
            name, args = 'get_procurement_risks', {'project_id': project, 'supplier': None}
        elif any(word in question for word in ['납기', '지연']):
            name, args = 'get_lead_time_status', {'project_id': project}
        elif any(word in question for word in ['규칙', '확인할 일', '룰']):
            name, args = 'evaluate_rules', {'project_id': project, 'as_of': None}
        else:
            name, args = 'get_project_summary', {'project_id': project}
        payload = json.loads(registry.execute(name, args))
        result = payload.get('result', [])
        docs = result if name == 'search_knowledge' else []
        text = f'{project or "전체 프로젝트"}의 정해진 문서·DB 조회 결과입니다. 아래 근거를 펼쳐 원본 값을 확인하세요.'
        if not result:
            text = '일치하는 기록을 찾지 못했습니다. 해당 내용은 미확인입니다.'
        return {'text': text, 'mode': 'demo', 'project_id': project, 'evidence': document_rows(docs),
                'data_evidence': [] if docs else [{'tool': name, 'arguments': args, 'payload': payload}], 'meta': meta()}

    @app.post('/api/realtime/tool')
    def realtime_tool(body: ToolCall):
        registry = KyungdongToolRegistry(repo())
        if body.name not in {item['name'] for item in registry.definitions}:
            raise HTTPException(400, '허용되지 않은 조회 도구입니다.')
        metadata = meta()
        output = json.loads(registry.execute(body.name, body.arguments))
        output['meta'] = metadata
        return {'output': json.dumps(output, ensure_ascii=False), 'meta': metadata}

    @app.post('/api/realtime/session')
    async def realtime_session(request: Request, project_id: Optional[str] = Query(default=None, max_length=80)):
        api_key = key()
        check_project(project_id)
        if request.headers.get('content-type', '').split(';')[0] != 'application/sdp':
            raise HTTPException(415, 'WebRTC 연결 정보가 필요합니다.')
        offer = await request.body()
        if not offer or len(offer) > 100_000:
            raise HTTPException(413, 'WebRTC 연결 정보 크기가 올바르지 않습니다.')
        try:
            sdp = offer.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise HTTPException(400, 'WebRTC 연결 정보가 올바르지 않습니다.') from exc
        registry = KyungdongToolRegistry(repo())
        session = {'type': 'realtime', 'model': os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1'),
                   'instructions': '경동글로벌텍 금속제조 업무 도우미입니다. 한국어로 짧게 답하세요. '
                   f"호출명은 {WAKE_POLICY['agent_name']}입니다. 호출명으로 시작한 질문에만 답하고, 호출명 없는 발화에는 아무 응답도 하지 마세요. "
                   '회사 사실은 반드시 조회 도구로 확인하세요. 근거 ID는 원본 레코드에 있는 project_id, material_lot, document_id 등 실제 식별자만 말하세요. '
                   'retrieved_at과 조회시각은 근거 ID가 아닙니다. 결과가 비어 있으면 선택 프로젝트에서 일치하는 기록을 찾지 못했다고 말하고 '
                   '근거 ID나 수량·단위를 만들지 마세요. 조회된 기록의 부재를 실제 재고가 0이라는 뜻으로 해석하지 마세요. '
                   '값과 단위는 원본에 있을 때만 말하세요. 답변은 두 문장 이내로 하고 조회시각은 사용자가 요청할 때만 읽으세요. '
                   '자료는 미승인 데모이며 없는 값은 미확인입니다. '
                   '설비 제어·발주·FAT 승인·출하 승인을 실행하지 마세요. 식별자가 불명확하면 재확인하세요. '
                   f'현재 선택 프로젝트: {project_id or "전체"}. 도구의 project_id에 이 값을 사용하세요.',
                   'tools': [{k: v for k, v in item.items() if k != 'strict'} for item in registry.definitions],
                   'output_modalities': ['audio'],
                   'audio': {'input': {'transcription': {'model': 'gpt-4o-mini-transcribe', 'language': 'ko'},
                                       'turn_detection': {'type': 'semantic_vad', 'eagerness': 'high', 'create_response': False, 'interrupt_response': False}},
                             'output': {'voice': os.getenv('OPENAI_REALTIME_VOICE', 'marin')}}}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                upstream = await client.post('https://api.openai.com/v1/realtime/calls',
                    headers={'Authorization': f'Bearer {api_key}'},
                    files={'sdp': (None, sdp, 'application/sdp'), 'session': (None, json.dumps(session), 'application/json')})
        except httpx.HTTPError as exc:
            raise HTTPException(502, '음성 서비스 연결에 실패했습니다.') from exc
        if upstream.is_error:
            raise HTTPException(502, '음성 모델 사용 권한과 서버 설정을 확인해 주세요.')
        return Response(upstream.text, media_type='application/sdp')

    dist = ROOT / 'v2/web/dist'
    if dist.exists():
        app.mount('/', StaticFiles(directory=dist, html=True), name='web')
    return app


app = create_app()
