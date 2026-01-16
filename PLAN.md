# Plan (Tauri + Python Sidecar 전환)

## 0. 준비 사항
- 현재 Tkinter UI는 유지(프로토타입/백업).
- 코어 로직은 Python에 유지하고 UI와 분리 유지.

## 0-1. 아키텍처 전환 (2026-01)
- Tauri IPC → HTTP/WebSocket 전환 [x]
  - FastAPI 서버 (`server/main.py`) 구현 [x]
  - WebSocket 실시간 진행률/결과 스트리밍 [x]
  - viewer-ui (Svelte) 새 프론트엔드 [x]
- SQLite 스레드 안전성 [x]
  - 워커 스레드별 DB 연결 생성 [x]
  - `create_new_db_connection()` 함수 추가 [x]

## 1. IPC 설계 (JSON Lines)
- 메시지 스키마 정의 [x]
  - 요청: {id, type:"run", op, payload}
  - 응답: ack/progress/result/log/done/error
- 작업 유형 정의 [x]
  - search/rename/move/build_nais/preset_load
- 진행도/ETA 표준화 [x]
- 취소(cancellation) 메시지 정의 [x]
- 버전 필드 추가(향후 호환성) [x]
- 예시 JSON 문서화 [x] (`IPC_SPEC.md`)

## 1-1. DB 설계(초안, SQLite)
- 스키마 정의 [x] (`db/schema.sql` 추가)
  - images(id, path, mtime, size, hash)
  - tags(image_id, tag)
  - matches(image_id, variable, status, values)
- templates/presets 테이블 추가 [x]
- 인덱스 설계 [x]
  - path/mtime/tag/variable/status
- 스캔 파이프라인 [x]
  - 최초 풀스캔 → DB 저장
  - 이후 증분 스캔(변경 파일만 재처리)
- 메타 테이블(schema_version) 추가 및 간단 마이그레이션 규칙 정의 [x]

## 2. Python Sidecar 구현
- stdin/stdout JSON Lines 루프 [x] (`sidecar/main.py`)
- 작업 큐/상태 관리 (job manager) [x]
- 멀티프로세스 병렬 처리 연결 [x]
- 중간 결과 스트리밍(result) [x] (scan/search)
- 오류/예외 처리 및 로그 [x] (error/log 메시지)
- 테스트용 CLI 스크립트 [x] (sidecar 직접 실행)
- scan/search 로컬 검증 [x]

## 2-1. core/ 리팩터링 계획(단계적)
- 1단계: 모듈 이동 계획 수립 및 import 경로 표준화 [x]
- 2단계: `core/` 서브패키지 생성 (extract/normalize/match/preset/utils) [x]
- 3단계: 기존 코드 이동 + 공개 API 재정의 (호환 레이어 유지) [x]
- 4단계: 테스트 경로 업데이트 및 회귀 확인 [x]
- 5단계: 문서/예시 경로 갱신 [x]

## 2-2. 병렬 처리 레이어 분리 계획
- 현재: `gui/tasks.py`에 병렬 처리 로직 존재
- 목표: sidecar 실행 레이어로 이동하여 UI/코어 분리 강화
- 작업:
  - `core/runner/` 또는 `sidecar/runner.py`에 병렬 실행 모듈화 [x]
  - 진행도/중간 결과 스트리밍 API 공통화 [x]
  - Tkinter/타우리 UI는 동일 API를 호출 [x]

## 2-3. DB 연동 계획
- sidecar 작업에서 DB 우선 조회 [x]
- 검색/필터는 DB 질의로 처리 [x]
- 태그 추출 결과는 DB에 캐시 [x]
- rename/move는 DB 태그 우선 사용 [x]
- UI에 필요한 최소 결과만 전송 [x]

## 2-4. 태그 저장/캐시 정책
- tags 테이블(행 단위) 기본 [x]
- 필요 시 images.tags_json 병행 저장 [x]
- 썸네일 캐시: cache/thumbs/ (해시 키) [x]

## 2-5. Tkinter → Sidecar IPC 전환
- 검색 탭: sidecar `search` 사용 [x]
- 검색 탭: DB 스캔 버튼 추가 [x]
- 파일명 변경 탭: sidecar `rename` 사용 [x]
- 폴더 분류 탭: sidecar `move` 사용 [x]
- @@@ 제거: sidecar `strip_suffix` 사용 [x]

## 3. Tauri UI 프로토타입
- 프레임워크: Svelte
- Svelte/Tauri 골격 + IPC 연결 준비 [x] (`ui/`)
- 파일/폴더 선택 다이얼로그 [x]
- 작업 탭 구조(편집/검색/파일명 변경/폴더 분류) [x]
- 결과 목록 + 미리보기 + 필터 [x]
- 진행도 표시/로그 뷰어 [x]
- IPC 연결 (spawn sidecar + 메시지 처리) [x]
- 사용자 친화 UX [x]
  - 작업 흐름 가이드(툴팁/도움말) [x]
  - 오류/충돌 상황 안내 강화 [x]
  - 대량 처리 중단/재시작 UX [x]

## 3-0. viewer-ui (새 프론트엔드, 2026-01)
- FastAPI + Svelte 웹 UI [x]
- 계층별 폴더 분류 (`variable_tree`) [x]
- 폴더 구조 썸네일 그리드 UI [x]
- 한글 이름순 정렬 [x]
- 디버그 로그 분리 (`--debug` 옵션) [x]
- 부분 분류 로직 (1층 OK → 1층 폴더로 이동) [x] (PARTIAL 상태)
- DeprecationWarning 수정 (lifespan handler) [x]

## 3-1. Svelte UI 구성안(초안)
- 화면 레이아웃
  - 좌측 네비게이션(편집/검색/파일명 변경/폴더 분류)
  - 우측 메인 작업 영역 + 하단 결과 패널
- 공통 컴포넌트
  - `ResultPanel`(필터/미리보기/스크롤) [x]
  - `ProgressBar`(진행/ETA) [x]
  - `LogPanel`(문제 로그/시스템 로그) [x]
  - `TemplateManager`(템플릿 불러오기/저장/상태 표시) [x]
  - `PresetImporter`(SDSTUDIO/NAIS/폴더 프리셋 → 변수 1개에 적용) [x]
- 작업별 컴포넌트
  - `EditorView`(변수/값/태그 편집, 공통 태그 제외, 일괄 변경) [x]
  - `SearchView`(태그 AND 검색) [x]
  - `RenameView`(템플릿/변수순서/드라이런) [x]
  - `MoveView`(단일 변수/대상 폴더 템플릿) [x]

## 3-2. Svelte 상태 관리/스토어 설계(초안)
- 전역 스토어
  - `templateStore`: 현재 템플릿/변수/값 상태 [x]
  - `jobStore`: 작업 상태(진행도/ETA/중단) [x]
  - `resultStore`: 결과 목록/필터/미리보기
  - `logStore`: 로그/문제 로그 경로
  - `logStore`/`resultStore` 기본 적용 [x]
- IPC 메시지 흐름
  - 요청 전송 → `jobStore` 초기화
  - `progress` → 진행도/ETA 업데이트
  - `result` → `resultStore` 누적
  - `done` → 상태 완료 처리
- 캐시 규칙
  - 공통 태그 캐시는 변수 이름 기준으로 저장
  - 결과 목록은 작업 단위로 분리 보관

## 3-3. 선택 보강(확장 옵션)
- 태그 출처 분리 저장(positive/negative/char) [x]
- 변수별 매칭 결과 캐시(DB)
- 대규모 스캔 성능 측정 지표 기록 [x]

## 4. 패키징/배포 [~]
- Python sidecar 빌드(PyInstaller 등) [x] (build.spec)
- Tauri 번들에 sidecar 포함 [-] (FastAPI로 대체)
- FastAPI 단독 exe 빌드 [x] (build.ps1, 32.5MB)
- Windows 경로/권한 테스트 [ ]
- 로그/문제 파일 위치 정리 [ ]

## 5. 성능/안정성 [ ]
- 대량 파일(10만+) 스트레스 테스트 [ ]
- 메모리 사용/큐 적체 점검 [ ]
- 취소/중단 시 안전 종료 [x]
- 충돌 파일명(@@@) 처리 확인 [x]

## 5-1. 작업 제어(중단/일시정지/재개) [ ]
- 1차: cancel 버튼(UI)로 즉시 중단 처리 [x]
- 2차: 작업 상태 저장/재개(작업 매니페스트 JSON 또는 SQLite)
  - 단계 분리: 계획 생성 → 적용 실행
  - 항목별 상태(대기/완료/실패) 기록 + 체크포인트
  - 재개 시 대기 항목만 재실행
  - rename/move 안전성 검증(중복/누락 방지)
  - rename/move 재개 모드(간단 체크포인트) [x]
  - 재개 파일 수동 삭제(UI) [x]

## 6. 문서화
- 사용자 가이드(임포트/공통 태그 제외/일괄 변경) [x]
- 개발자 가이드(IPC 메시지/코어 구조) [x]
- 폴더 구조/모듈 역할 문서화 [x]

## 7. 테스트 전략
- unittest 기반 유지, pytest 이식 가능한 구조로 분리
- pytest 전환 시:
  - conftest.py로 공통 설정 이동
  - fixtures/parametrize 적용
  - CI에서 pytest 실행 추가

## 7-1. 디버깅/검증 도구 제안 (debug/ 폴더)
- `debug/inspect_exif.py`: EXIF/스텔스 태그 수동 확인 [x]
- `debug/ipc_echo.py`: IPC 메시지 송수신 테스트(에코 서버) [x]
- `debug/db_smoke.py`: DB 스키마 생성/간단 쿼리 검증 [x]
- `debug/thumb_cache.py`: 썸네일 캐시 생성/정리 테스트 [x]
- `debug/perf_extract.py`: EXIF 추출/정규화 성능 측정 [x]
- `debug/perf_db.py`: DB 검색 성능 측정 [x]

## 7-2. IPC/DB 관련 테스트 아이디어
- IPC 메시지 파서(부분 라인/깨진 JSON) 복원 테스트
- 취소 요청 시 작업 중단/정리 테스트
- DB 증분 스캔(변경 파일만 재처리) 검증
- 태그 저장 방식별 검색 성능 비교
- IPC emitter 버전 포함 테스트 [x]
- DB 쿼리 기본 동작 테스트 [x]

## 8. 배포 전 준비(레포 정리)
- requirements.txt 추가 및 CI에서 사용
