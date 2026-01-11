# Plan (Tauri + Python Sidecar 전환)

## 0. 준비 사항
- 현재 Tkinter UI는 유지(프로토타입/백업).
- 코어 로직은 Python에 유지하고 UI와 분리 유지.

## 1. IPC 설계 (JSON Lines)
- 메시지 스키마 정의
  - 요청: {id, type:"run", op, payload}
  - 응답: ack/progress/result/log/done/error
- 작업 유형 정의
  - search/rename/move/build_nais/preset_load
- 진행도/ETA 표준화
- 취소(cancellation) 메시지 정의
- 버전 필드 추가(향후 호환성)
- 예시 JSON 문서화

## 1-1. DB 설계(초안, SQLite)
- 스키마 정의
  - images(id, path, mtime, size, hash)
  - tags(image_id, tag)
  - matches(image_id, variable, status, values)
- 인덱스 설계
  - path/mtime/tag/variable/status
- 스캔 파이프라인
  - 최초 풀스캔 → DB 저장
  - 이후 증분 스캔(변경 파일만 재처리)
- 메타 테이블(schema_version) 추가 및 간단 마이그레이션 규칙 정의

## 2. Python Sidecar 구현
- stdin/stdout JSON Lines 루프
- 작업 큐/상태 관리 (job manager)
- 멀티프로세스 병렬 처리 연결
- 중간 결과 스트리밍(result)
- 오류/예외 처리 및 로그
- 테스트용 CLI 스크립트

## 2-1. core/ 리팩터링 계획(단계적)
- 1단계: 모듈 이동 계획 수립 및 import 경로 표준화
- 2단계: `core/` 서브패키지 생성 (extract/normalize/match/preset/utils)
- 3단계: 기존 코드 이동 + 공개 API 재정의 (호환 레이어 유지)
- 4단계: 테스트 경로 업데이트 및 회귀 확인
- 5단계: 문서/예시 경로 갱신

## 2-2. 병렬 처리 레이어 분리 계획
- 현재: `gui/tasks.py`에 병렬 처리 로직 존재
- 목표: sidecar 실행 레이어로 이동하여 UI/코어 분리 강화
- 작업:
  - `core/runner/` 또는 `sidecar/runner.py`에 병렬 실행 모듈화
  - 진행도/중간 결과 스트리밍 API 공통화
  - Tkinter/타우리 UI는 동일 API를 호출

## 2-3. DB 연동 계획
- sidecar 작업에서 DB 우선 조회
- 검색/필터는 DB 질의로 처리
- 태그 추출 결과는 DB에 캐시
- UI에 필요한 최소 결과만 전송

## 2-4. 태그 저장/캐시 정책
- tags 테이블(행 단위) 기본
- 필요 시 images.tags_json 병행 저장
- 썸네일 캐시: cache/thumbs/ (해시 키)

## 3. Tauri UI 프로토타입
- 프레임워크: Svelte
- 파일/폴더 선택 다이얼로그
- 작업 탭 구조(편집/검색/파일명 변경/폴더 분류)
- 결과 목록 + 미리보기 + 필터
- 진행도 표시/로그 뷰어
- IPC 연결 (spawn sidecar + 메시지 처리)
- 사용자 친화 UX
  - 작업 흐름 가이드(툴팁/도움말)
  - 오류/충돌 상황 안내 강화
  - 대량 처리 중단/재시작 UX

## 3-1. Svelte UI 구성안(초안)
- 화면 레이아웃
  - 좌측 네비게이션(편집/검색/파일명 변경/폴더 분류)
  - 우측 메인 작업 영역 + 하단 결과 패널
- 공통 컴포넌트
  - `ResultList`(필터/미리보기/스크롤)
  - `ProgressBar`(진행/ETA)
  - `LogPanel`(문제 로그/시스템 로그)
  - `PresetManager`(프리셋 불러오기/저장/상태 표시)
- 작업별 컴포넌트
  - `EditorView`(변수/값/태그 편집, 공통 태그 제외, 일괄 변경)
  - `SearchView`(태그 AND 검색)
  - `RenameView`(템플릿/변수순서/드라이런)
  - `MoveView`(단일 변수/대상 폴더 템플릿)

## 3-2. Svelte 상태 관리/스토어 설계(초안)
- 전역 스토어
  - `presetStore`: 현재 프리셋/변수/값 상태
  - `jobStore`: 작업 상태(진행도/ETA/중단)
  - `resultStore`: 결과 목록/필터/미리보기
  - `logStore`: 로그/문제 로그 경로
- IPC 메시지 흐름
  - 요청 전송 → `jobStore` 초기화
  - `progress` → 진행도/ETA 업데이트
  - `result` → `resultStore` 누적
  - `done` → 상태 완료 처리
- 캐시 규칙
  - 공통 태그 캐시는 변수 이름 기준으로 저장
  - 결과 목록은 작업 단위로 분리 보관

## 3-3. 선택 보강(확장 옵션)
- 태그 출처 분리 저장(positive/negative/char)
- 변수별 매칭 결과 캐시(DB)
- 대규모 스캔 성능 측정 지표 기록

## 4. 패키징/배포
- Python sidecar 빌드(PyInstaller 등)
- Tauri 번들에 sidecar 포함
- Windows 경로/권한 테스트
- 로그/문제 파일 위치 정리

## 5. 성능/안정성
- 대량 파일(10만+) 스트레스 테스트
- 메모리 사용/큐 적체 점검
- 취소/중단 시 안전 종료
- 충돌 파일명(@@@) 처리 확인

## 6. 문서화
- 사용자 가이드(임포트/공통 태그 제외/일괄 변경)
- 개발자 가이드(IPC 메시지/코어 구조)
- 폴더 구조/모듈 역할 문서화

## 7. 테스트 전략
- unittest 기반 유지, pytest 이식 가능한 구조로 분리
- pytest 전환 시:
  - conftest.py로 공통 설정 이동
  - fixtures/parametrize 적용
  - CI에서 pytest 실행 추가

## 7-1. 디버깅/검증 도구 제안 (debug/ 폴더)
- `debug/inspect_exif.py`: EXIF/스텔스 태그 수동 확인
- `debug/ipc_echo.py`: IPC 메시지 송수신 테스트(에코 서버)
- `debug/db_smoke.py`: DB 스키마 생성/간단 쿼리 검증
- `debug/thumb_cache.py`: 썸네일 캐시 생성/정리 테스트

## 7-2. IPC/DB 관련 테스트 아이디어
- IPC 메시지 파서(부분 라인/깨진 JSON) 복원 테스트
- 취소 요청 시 작업 중단/정리 테스트
- DB 증분 스캔(변경 파일만 재처리) 검증
- 태그 저장 방식별 검색 성능 비교

## 8. 배포 전 준비(레포 정리)
- requirements.txt 추가 및 CI에서 사용
