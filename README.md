# 경동글로벌텍 Agent Cockpit · 제조 AI Agent

주문형 금속 장치의 **수주·견적 → 설계 → 구매·입고검사 → 레이저커팅·포밍 → 용접·조립 → FAT·시운전 → 출하·설치** 이력을 대화 중심 화면에서 연결하는 실행형 Streamlit 프로토타입입니다.

## Agent Cockpit 화면

- 상단: 진행 프로젝트·자재·구매·FAT·납기 핵심지표
- 왼쪽: 새 대화, 최근 질문 이력, 업무영역별 추천질문
- 가운데: 문서·Data Hub 근거가 표시되는 Agent 채팅
- 오른쪽: 선택 프로젝트 진척·납기·종합위험·승인대기
- 사이드바: 모델·검색범위·견적/설계/자재/FAT 문서 인덱싱

추천질문, 과거 질문, 프로젝트 브리핑 버튼은 모두 동일한 채팅 실행경로를 사용합니다.

## 핵심 기능

- 프로젝트·도면 Revision·ECR/ECO·공정 진척 통합 조회
- 자재 LOT·바코드·MTC·발주서/거래명세서 연결 및 입고검사 예외 탐지
- 견적 원가·납기·수익성·위험도 데모와 유사 프로젝트 추천
- 공급사 납기 위험·대체 후보, FAT 반복 불량·클레임 추적
- OpenAI Responses API의 읽기 전용 Function Calling과 File Search 기반 RAG
- 초기 조회 → 6개월 학습·추천 → 2년 경보·예측 로드맵

> 화면의 프로젝트, 고객, 측정치, 예측값은 검증용 가상 데이터입니다. 평균 납기 90일, 연간 약 50대, 레이저커팅 4일→1일은 제공된 기준정보입니다. 견적시간 50% 단축과 원가오차 10% 이하는 목표이며 달성 실적이 아닙니다.

## 실행

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

기본 실행은 로컬 PostgreSQL + pgvector를 사용합니다. `DATABASE_URL`을 비워두면 테스트·오프라인용 SQLite로 자동 전환됩니다. RAG Agent와 문서 인덱싱에는 `.env`의 `OPENAI_API_KEY`가 필요합니다.

### 로컬 PostgreSQL + pgvector

PostgreSQL 17과 pgvector가 설치되어 있다면 다음처럼 클러스터를 시작하고 기존 SQLite 데모 DB를 이관할 수 있습니다. (이 저장소의 기본 개발 환경은 55432 포트를 사용합니다.)

```bash
brew install postgresql@17 pgvector
initdb -D data/postgres --auth=trust --username="$USER" \
  -c shared_memory_type=mmap -c dynamic_shared_memory_type=mmap
pg_ctl -D data/postgres -o "-p 55432 -h 127.0.0.1" -l data/postgres.log start
createdb -h 127.0.0.1 -p 55432 -U "$USER" kgt_cockpit
export DATABASE_URL="postgresql://$USER@127.0.0.1:55432/kgt_cockpit"
python scripts/migrate_sqlite_to_postgres.py --source data/kyungdong_demo.db
streamlit run app.py
```

마이그레이션은 업무 테이블, 룰, 지식문서, 앱 설정을 반복 실행해도 안전하게 병합합니다. `knowledge_documents.embedding`은 1536차원 `vector` 컬럼과 HNSW 코덱으로 준비되어 있으며, 임베딩을 제공하는 호출자는 `PostgresRepository.vector_search_knowledge()`를 사용할 수 있습니다.

## 데모 질문

- `KGT-26002 납기 위험과 대안을 알려줘`
- `입고검사 보류 자재, 문서 누락, 필요한 승인 조치를 알려줘`
- `KGT-26001 FAT 불합격 원인을 클레임 이력과 비교해줘`
- `진공건조기 견적의 위험과 예상 수익성을 보여줘`

`sample_docs/`의 예시 문서를 지식문서 탭에서 올리면 Data Hub 조회와 사내 문서 검색을 함께 시험할 수 있습니다.

## 구조

```text
app.py                       Streamlit UI
kyungdong_agent/data_hub.py  PostgreSQL+pgvector/SQLite 어댑터·스키마·조회
kyungdong_agent/factory_tools.py  읽기 전용 도구 스키마/실행
scripts/migrate_sqlite_to_postgres.py  SQLite → PostgreSQL 데이터 이관
kyungdong_agent/service.py   Responses API 도구 호출 루프·File Search
sample_docs/                 견적·자재·FAT 예시 지식문서
tests/                       저장소·Agent 단위 테스트
skills/manufacturing-agent-maker/  다른 제조기업에 재사용할 Agent Maker 스킬
```

## 운영 전 필수 확인

1. ERP/Excel/CAD/PDM 원천, 키 체계, 실제 설비 태그·단위·수집주기·통신방식 확정
2. 종료 프로젝트의 실제 원가·공수·납기·FAT·클레임 라벨 품질 진단
3. 위험성평가, SOP, LOTO, 계측기 교정, 고온·고압·진공·회전체 경보 승인체계 연동
4. 견적·발주·대체자재·FAT·출하에 Human-in-the-loop 승인 적용
5. 최소권한, 감사로그, 암호화, 백업/복구, 모델 평가·드리프트·재학습·롤백 적용

## 테스트

```bash
pytest -q
python -m py_compile app.py kyungdong_agent/*.py
```
