# 경동글로벌텍 AI Agent V2

`new-agent-maker`의 2026-09-28 기준을 적용한 React 19 · TypeScript · Vite 7 · FastAPI 화면입니다. 기존 Streamlit 앱과 경동글로벌텍의 읽기 전용 저장소·조회 도구를 재사용합니다. 니즈푸드의 급식/김치 데이터 모델은 사용하지 않습니다.

## 실행

프로젝트 루트에서 실행합니다. Python 3.12 권장(현재 로컬 Python 3.9에서도 테스트), Node 22.12 이상이 필요합니다.

```bash
.venv/bin/pip install -r v2/requirements.txt
npm ci --prefix v2/web
npm run build --prefix v2/web
DATABASE_URL='' .venv/bin/python -m uvicorn v2.api:app --host 127.0.0.1 --port 8511
```

접속: http://127.0.0.1:8511. 위 명령은 기존 SQLite 데모 DB를 사용합니다. PostgreSQL을 사용하려면 `DATABASE_URL=''` 접두사를 제거하고 루트 `.env`에 실제 연결 정보를 설정하세요. 기존 `create_repository`가 PostgreSQL 어댑터를 선택하며, 이번 변경에서 PostgreSQL 실행 검증은 하지 않았습니다.

프런트 개발은 별도 터미널에서 `npm run dev --prefix v2/web`로 실행합니다. Vite의 `/api` 프록시는 8511 포트입니다. 기존 8510 포트가 사용 중이라 경동 V2의 기본 포트를 8511로 분리했습니다.

## 사용자 흐름

- 왼쪽: 지식문서 검색과 본문, 데이터허브 원본 테이블(10개씩 탐색).
- 중앙: 전체/프로젝트 선택, 대화, 근거 펼침, 새 대화, 실시간 음성.
- 오른쪽: 생산·품질 10개 / 문서·규칙 10개 추천질문, 세션별 최근 질문 20개.
- 모바일: 자료·질문 버튼으로 보조 패널을 열고 닫습니다.
- 직접 입력·추천질문·이력 재질문은 같은 요청 경로를 사용합니다. 이력은 원래 프로젝트를 함께 복원합니다.
- 프로젝트 변경·새 대화는 요청을 취소하고 늦게 도착하는 응답을 무시하며 마이크를 종료합니다. 서버가 이미 시작한 유료 요청까지 취소되는 것은 아닙니다.
- 데모는 키워드로 정해진 조회 도구를 선택합니다. 임의 질문의 의미를 AI로 분석하지 않습니다. AI 분석은 기존 Responses 도구 루프를 호출하고 최근 최대 12개 대화 메시지를 전달합니다.
- 프로젝트와 자재 LOT는 별개 식별자입니다. 수량·두께·공수·FAT 측정 단위는 원본 레코드로 확인합니다.

## 연결과 접근 제어

루트 `.env`를 읽습니다. 필요한 환경변수는 `v2/.env.example`에 있습니다. API 키는 서버에만 둡니다. 화면 설정의 접근 코드는 API 키와 별개이며 sessionStorage에 저장합니다.

로컬 예외는 연결 상대 IP와 요청 hostname이 모두 loopback일 때만 허용합니다. 외부 API 접속은 데모 조회를 포함해 `COCKPIT_ACCESS_TOKEN`이 필요합니다. 공유 접근 코드는 사용자 계정·조직 권한 시스템이 아닙니다. 신뢰 프록시 환경에서는 실제 클라이언트 IP 처리와 별도 사용자 인증을 배포자가 구성해야 합니다.

`DATABASE_URL` 지정 여부에 따라 기존 PostgreSQL/SQLite 어댑터를 선택합니다. 데이터는 모두 검증용 가상 자료이며 문서는 미승인 샘플로 표시됩니다. 실제 회사 데이터를 연결하면 출처·승인 상태·demo_data 메타데이터도 함께 변경해야 합니다.

실시간 음성은 WebRTC와 발화 종료 감지·끼어들기·음소거·종료를 지원하도록 구현했습니다. 실제 경동 조회 도구 스키마와 서버 핸들러를 제공하고 도구 결과는 화면 근거에도 남깁니다. 센서 스트리밍/설비 제어 기능은 포함하지 않습니다. HTTPS 또는 localhost와 마이크 권한이 필요합니다.

공식 구현 참고: [OpenAI WebRTC 연결](https://developers.openai.com/api/docs/guides/voice-webrtc). 모델 가용성과 유료 호출은 해당 계정에서 확인해야 합니다.

## 검증

```bash
.venv/bin/python -m pytest tests v2/tests -q
npm run build --prefix v2/web
```

기존 테스트 28개 통과·1개 건너뜀에서 API 테스트 7개를 추가했습니다. 합계 35개 통과·1개 건너뜀입니다. API 테스트는 임시 DB와 모의 음성 서버를 사용하며 실제 유료 호출을 수행하지 않습니다.

실제 유료 AI·음성, 마이크 실기기, PostgreSQL, Docker 배포는 이번 검증 대상에서 실행하지 않았습니다. 기존 루트 Docker/Compose는 Streamlit V1용입니다. V2 외부 배포는 별도 구성이 필요합니다.

브라우저 검증도 완료했습니다: 1440px 데스크톱 / 390px 모바일에서 문서 검색·본문, 테이블, 직접 입력·추천질문·이력 재질문, 프로젝트 전환, 새 대화와 근거 표시, 가로 넘침을 확인했습니다. 모의 WebRTC로 연결 실패 시 마이크 해제, 음소거/해제, 종료 후 트랙 정리와 지연 응답의 문맥 격리를 확인했습니다. 실제 음성 인식 품질·끼어들기 오디오 동작을 검증했다는 의미는 아닙니다.

서버가 실행 중이고 Playwright와 Chromium이 설치된 환경에서는 다음으로 브라우저 검증을 다시 실행할 수 있습니다. 별도 설치 위치는 `PLAYWRIGHT_MODULE` 환경변수로 지정할 수 있습니다. 기본 접속 주소를 바꾸려면 `KGT_URL`을 지정합니다.

```bash
node v2/tests/browser-smoke.cjs
node v2/tests/browser-lifecycle.cjs
```


## Hostinger Docker Manager

`docker-compose.v2.yml`과 `v2/Dockerfile`은 기존 `경동 조종석`(8501)을 재시작하지 않고 포트 8511에 V2를 별도 배포하도록 구성했습니다. SQLite 데모 DB는 named volume에 유지되고 샘플 데이터로 초기화됩니다. PostgreSQL 접속과 운영 데이터는 구성하지 않습니다.

새 애플리케이션 이름은 `kyungdong-agent-v2`로 사용합니다. Hostinger의 Docker Manager는 Compose YAML의 `build.context: .`에 대응하는 소스 트리가 필요하므로 V2 변경을 저장소에 푸시한 후 해당 Compose 파일과 저장소 빌드 컨텍스트를 연결해야 합니다. 배포 환경에 `COCKPIT_ACCESS_TOKEN` 값을 지정하지 않으면 Compose 변수 검증 단계에서 시작을 거부합니다. 이 값은 외부 API 요청을 보호하며 앱 화면의 접근 코드 입력란에 같은 값을 입력합니다. OpenAI 기능은 `OPENAI_API_KEY` 서버 환경변수가 설정된 경우에만 활성화됩니다.
