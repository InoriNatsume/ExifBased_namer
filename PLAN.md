# PLAN

## TODO (앞으로 해야 할 것들)

### 패키징/배포
- [ ] Windows 경로/권한 테스트
- [ ] 로그/문제 파일 위치 정리

### 성능/안정성
- [ ] 대량 파일(10만+) 스트레스 테스트
- [ ] 메모리 사용/큐 적체 점검

### 작업 제어 고도화
- [ ] 작업 상태 저장/재개 (작업 매니페스트 JSON 또는 SQLite)
  - 단계 분리: 계획 생성 → 적용 실행
  - 항목별 상태(대기/완료/실패) 기록 + 체크포인트
  - 재개 시 대기 항목만 재실행
  - rename/move 안전성 검증(중복/누락 방지)

---

## Changelog (완료된 항목)

### 2026-01-27
- [x] 문서 통합 (README.md로 모든 문서 병합)
- [x] PLAN.md 형식 변경 (TODO + Changelog)
- [x] docs/ 폴더 삭제, DESIGN.md/API_SPEC.md 삭제

### 2026-01-26
- [x] IPC_SPEC.md → API_SPEC.md 이름 변경 및 FastAPI 스펙으로 업데이트
- [x] build/, dist/ Git에서 제거 (80MB+ 실수 커밋)
- [x] .gitignore에 빌드 산출물 추가
- [x] pytest conftest.py 공유 fixtures 생성
- [x] GitHub Actions CI 매트릭스 확장 (Python 3.11/3.12/3.13)
- [x] requirements.txt 줄바꿈 형식 수정
- [x] pyproject.toml 생성 (pytest/ruff 설정)

### 2026-01-25
- [x] DeprecationWarning 수정 (FastAPI lifespan handler)
- [x] 부분 분류 로직 (1층 OK → PARTIAL 상태)
- [x] PyInstaller 빌드 스크립트 (build.ps1, build.spec) → 32.5MB exe
- [x] 폴더 분류 move 패널 에러 수정

### 2026-01 (아키텍처 전환)
- [x] Tauri IPC → HTTP/WebSocket 전환
- [x] FastAPI 서버 (`server/main.py`) 구현
- [x] WebSocket 실시간 진행률/결과 스트리밍
- [x] viewer-ui (Svelte) 새 프론트엔드
- [x] SQLite 스레드 안전성 (워커별 DB 연결)
- [x] 계층별 폴더 분류 (`variable_tree`)
- [x] 폴더 구조 썸네일 그리드 UI
- [x] 한글 이름순 정렬
- [x] 디버그 로그 분리 (`--debug` 옵션)

### core/ 리팩터링
- [x] 모듈 이동 계획 수립 및 import 경로 표준화
- [x] `core/` 서브패키지 생성 (extract/normalize/match/preset/utils)
- [x] 기존 코드 이동 + 공개 API 재정의 (호환 레이어 유지)
- [x] 테스트 경로 업데이트 및 회귀 확인
- [x] 문서/예시 경로 갱신

### 병렬 처리 레이어 분리
- [x] `core/runner/`에 병렬 실행 모듈화
- [x] 진행도/중간 결과 스트리밍 API 공통화
- [x] Tkinter/타우리 UI 동일 API 호출

### DB 연동
- [x] sidecar 작업에서 DB 우선 조회
- [x] 검색/필터는 DB 질의로 처리
- [x] 태그 추출 결과는 DB에 캐시
- [x] rename/move는 DB 태그 우선 사용
- [x] 필요한 최소 결과만 UI 전송

### 태그 저장/캐시
- [x] tags 테이블(행 단위) 기본
- [x] images.tags_json 병행 저장
- [x] 썸네일 캐시: cache/thumbs/ (해시 키)

### Tkinter → Sidecar IPC 전환
- [x] 검색 탭: sidecar `search` 사용
- [x] 검색 탭: DB 스캔 버튼 추가
- [x] 파일명 변경 탭: sidecar `rename` 사용
- [x] 폴더 분류 탭: sidecar `move` 사용
- [x] @@@ 제거: sidecar `strip_suffix` 사용

### Python Sidecar 구현
- [x] stdin/stdout JSON Lines 루프 (`sidecar/main.py`)
- [x] 작업 큐/상태 관리 (job manager)
- [x] 멀티프로세스 병렬 처리 연결
- [x] 중간 결과 스트리밍 (scan/search)
- [x] 오류/예외 처리 및 로그
- [x] 테스트용 CLI 스크립트
- [x] scan/search 로컬 검증

### IPC 설계
- [x] 메시지 스키마 정의 (요청: {id, type, op, payload}, 응답: ack/progress/result/log/done/error)
- [x] 작업 유형 정의 (search/rename/move/build_nais/preset_load)
- [x] 진행도/ETA 표준화
- [x] 취소 메시지 정의
- [x] 버전 필드 추가
- [x] 예시 JSON 문서화

### DB 설계 (SQLite)
- [x] 스키마 정의 (`db/schema.sql`)
- [x] images/tags/matches 테이블
- [x] templates/presets 테이블
- [x] 인덱스 설계 (path/mtime/tag/variable/status)
- [x] 스캔 파이프라인 (풀스캔 → 증분)
- [x] 메타 테이블(schema_version) 및 마이그레이션 규칙

### Tauri UI 프로토타입
- [x] Svelte/Tauri 골격 + IPC 연결
- [x] 파일/폴더 선택 다이얼로그
- [x] 작업 탭 구조 (편집/검색/파일명 변경/폴더 분류)
- [x] 결과 목록 + 미리보기 + 필터
- [x] 진행도 표시/로그 뷰어
- [x] 사용자 친화 UX (툴팁/도움말, 오류 안내, 중단/재시작)

### Svelte UI 컴포넌트
- [x] ResultPanel (필터/미리보기/스크롤)
- [x] ProgressBar (진행/ETA)
- [x] LogPanel (문제 로그/시스템 로그)
- [x] TemplateManager (템플릿 불러오기/저장/상태)
- [x] PresetImporter (SDSTUDIO/NAIS/폴더 → 변수 적용)
- [x] EditorView (변수/값/태그 편집, 공통 태그 제외)
- [x] SearchView (태그 AND 검색)
- [x] RenameView (템플릿/변수순서/드라이런)
- [x] MoveView (단일 변수/대상 폴더 템플릿)

### Svelte 상태 관리
- [x] templateStore (현재 템플릿/변수/값)
- [x] jobStore (작업 상태/진행도/ETA/중단)
- [x] logStore/resultStore 기본 적용

### 선택 보강
- [x] 태그 출처 분리 저장 (positive/negative/char)
- [x] 대규모 스캔 성능 측정 지표 기록

### 작업 제어 (1차)
- [x] cancel 버튼으로 즉시 중단 처리
- [x] rename/move 재개 모드 (간단 체크포인트)
- [x] 재개 파일 수동 삭제 (UI)

### 안정성
- [x] 취소/중단 시 안전 종료
- [x] 충돌 파일명(@@@) 처리 확인

### 디버깅/검증 도구 (debug/)
- [x] `debug/inspect_exif.py` - EXIF/스텔스 태그 확인
- [x] `debug/ipc_echo.py` - IPC 메시지 테스트
- [x] `debug/db_smoke.py` - DB 스키마 검증
- [x] `debug/thumb_cache.py` - 썸네일 캐시 테스트
- [x] `debug/perf_extract.py` - EXIF 성능 측정
- [x] `debug/perf_db.py` - DB 검색 성능 측정

### 테스트
- [x] IPC emitter 버전 포함 테스트
- [x] DB 쿼리 기본 동작 테스트
- [x] 26개 자동 테스트 (pytest/unittest)

### 문서화
- [x] 사용자 가이드 (임포트/공통 태그 제외/일괄 변경)
- [x] 개발자 가이드 (IPC 메시지/코어 구조)
- [x] 폴더 구조/모듈 역할 문서화

### 배포 준비
- [x] requirements.txt 추가 및 CI에서 사용
- [x] PyInstaller 단독 exe 빌드 (32.5MB)
