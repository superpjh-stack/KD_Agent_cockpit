# 코드 재사용과 검증

## 동봉 소스

`../assets/starter/`는 대화에서 수정한 경동글로벌텍 V2 소스의 스냅샷이다. `source-manifest.json`은 파일별 SHA-256이다. 키·.env·기존 DB·node_modules·가상환경·dist·Git 이력은 포함하지 않았다. Dockerfile은 기존 DB 파일을 COPY하지 않고 저장소의 샘플 초기화 기능을 사용하게 조정했다.

새 대상 디렉터리에 필요한 소스를 복사하고 그 디렉터리에서 작업한다. 스킬 내부를 실행 작업공간으로 사용하지 않는다. 기존 프로젝트에는 전체 복사하지 말고 diff를 검토해 필요한 모듈만 이식한다.

## 핵심 파일

- `kyungdong_agent/compound_graph.py`: 요청별 StateGraph, 최대 2회 계획·12회 조회, 조회 동시성 3, 90초 예산, 계획 검증·중복 제거, 답변 검증과 음성 요약.
- `conversation_context.py`: 후속 질문의 프로젝트 범위와 원본 비교표.
- `factory_tools.py`, `data_hub.py`: 허용 도구와 저장소. 회사별 데이터 연결 시 가장 먼저 검토한다.
- `compound_questions.py`, `v2/api.py`: 복합질문 및 기존 20개 질문, 인증·텍스트·음성 API.
- `v2/web/src/hooks/useRealtimeVoice.ts`: WebRTC, 발화별 세대 번호, 이전 응답 무시, 마이크 정리.
- `v2/web/src/App.tsx`, `styles.css`: 패널 구성, 비교표, 요청별 근거, 답변 시작점 스크롤.
- `sample_docs/knowledge`: 미승인 가상 샘플. 회사의 승인 자료로 교체하기 전 실제 규정으로 사용하지 않는다.

## 실행

Python 3.12 환경과 Node를 사용한다. 버전·SDK·Realtime 이벤트를 변경할 때는 당시 공식 문서를 확인한다. 모델은 서버 환경변수를 우선하며 최신 이름을 임의로 추측하지 않는다.

```sh
uv venv --python python3.12 .venv-v2
uv pip install --python .venv-v2/bin/python -r v2/requirements.txt pytest
npm --prefix v2/web ci
npm --prefix v2/web run build
.venv-v2/bin/python -m pytest v2/tests -q
```

로컬 SQLite 실행 예:

```sh
DATABASE_URL='' .venv-v2/bin/python -m uvicorn v2.api:app --host 127.0.0.1 --port 8512
```

DB 디렉터리와 샘플은 저장소가 초기화한다. 기존 DB를 지정할 때는 초기화·마이그레이션 동작을 먼저 검토한다. `start-v2.sh`는 SQLite와 0.0.0.0:8511을 기본 사용하므로 환경 의도에 맞게 수정한다. `OPENAI_API_KEY`, 선택적 `OPENAI_MODEL`, `OPENAI_REALTIME_MODEL`, `OPENAI_REALTIME_VOICE`, 외부 접속용 `COCKPIT_ACCESS_TOKEN`은 서버에서 설정한다. 비밀값을 문서·로그·스킬에 넣지 않는다.

## 회귀 검증

- 복합질문에서 자재+FAT+문서가 함께 조회되는지, AI 계획에서 빠진 분야가 보완되는지 확인한다.
- 잘못된 도구·인자·프로젝트 확장을 막고, 한 도구 실패에도 나머지 근거를 보존한다.
- 답변의 실제 인용과 유효한 근거가 없는 요청은 해결됐다고 표시하지 않는다.
- 후속 질문은 동일 프로젝트를 유지하고 여러 대상이면 확인 질문한다. 새 대화의 문맥은 비어 있어야 한다.
- 비교표는 0, null, 단위, 프로젝트 ID를 보존한다.
- 느린 도구 호출 중 새 발화를 주입하고 이전 텍스트·근거가 나타나지 않는지 확인한다. 마이크 해제·음소거·세션 전환도 점검한다.
- 1440px와 390px에서 패널, 비교표 가로 스크롤, 하단 입력창, 긴 답변 시작점 고정을 확인한다.

`browser-lifecycle.cjs`는 모의 음성 테스트다. `browser-live.cjs`는 유료 실제 서비스 호출을 포함할 수 있으므로 실행 전 내용을 검토한다. `browser-smoke.cjs`는 과거 프로젝트 선택 UI를 참조하므로 현재 UI에 맞게 수정한 뒤 사용한다. 이 파일이 존재한다는 이유만으로 전체 브라우저 테스트가 현재 통과했다고 보고하지 않는다.

## 현재 한계

- 의미 기반 답변 누락 검사는 모델 판단과 인용·인덱스 검사를 함께 사용한다. 근거가 의미적으로 주장을 입증하는지 또는 계산이 맞는지 완전하게 증명하지 않는다.
- 프로젝트 문맥은 최근 사용자 발화의 명시적 ID와 일부 한국어 지시 표현에 기반한다. 모든 생략형 후속 질문을 해결하거나 세션을 영구 저장하는 방식은 아니다.
- 동작 중인 DB 스레드·서버 모델 호출은 브라우저 취소로 반드시 종료되지 않는다. 비용 취소를 보장하지 않는다.
- 비교표는 납기·예상 원가·자재·FAT 분야를 지원한다. 추가 분야는 원본 스키마에 맞는 표 어댑터를 추가한다.
- 음성 연결 실패·끼어들기는 모의 검증과 실제 기기 검증을 구별한다. 실제 모바일 HTTPS/권한/오디오 재생 검증은 별도로 수행한다.
- 읽기 전용 시스템이다. 설비 제어·발주·승인·출하 실행은 구현 범위에 포함되지 않는다.
