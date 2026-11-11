# Hostinger V2 배포

- VPS: 1934103 / srv1934103.hstgr.cloud
- HTTPS: https://srv1934103.hstgr.cloud/kd-agent/
- 애플리케이션 이미지: kyungdong-agent-v2:fa25179
- 배포 디렉터리: /docker/kyungdong-agent-v2
- 소스 릴리스: /docker/kyungdong-agent-v2/releases/fa25179
- 컨테이너: kyungdong-agent-v2 / 포트 8511
- 기존 runtime.env와 데이터 볼륨을 유지한다. 비밀 설정은 Git에 포함하지 않는다.

프런트엔드는 상대 asset base와 apiPath를 사용해 / 및 /kd-agent/에서 동작한다. Caddy의 /kd-agent/* 경로는 prefix를 제거하고 호스트 게이트웨이 172.16.11.1:8511로 전달한다. Caddy 네트워크를 재생성할 경우 게이트웨이 주소와 upstream 접근을 다시 확인해야 한다. 다른 서비스 경로는 보존했다.

검증: HTTPS 화면 200, 인증 없는 workspace 401, 인증한 workspace와 복합조회 정상, 질문 세 그룹 각 10개, LangGraph 비교표 반환, 컨테이너 healthy. Chrome 모바일 390px 화면·정적 자산·secure context 확인. 실제 마이크 음성 품질은 별도 검증 대상이다.

롤백 자료:
- 이전 이미지 kyungdong-agent-v2:1903d3f
- /docker/kyungdong-agent-v2/docker-compose.before-031af13.yml
- /docker/rodem-mes/Caddyfile.before-kd-031af13
- 기존 데이터 볼륨의 backup-before-031af13.db (SQLite backup API로 생성)

서비스 롤백 시 이전 Compose를 복원해 해당 서비스만 재생성한다. 데이터 복원은 기존 DB와 변경 내역을 먼저 검토한 뒤 별도로 수행한다. 이전 UI는 subpath를 지원하지 않으므로 이미지 롤백 시 Caddy 경로도 함께 검토한다.

서버 실호출에서 JSON 응답 형식의 input 명시 요구를 확인해 fa25179에서 수정했다. 기존 instruction 외에 입력 JSON에도 응답 형식을 명시한다.
