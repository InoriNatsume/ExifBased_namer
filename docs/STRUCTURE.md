# 폴더 구조

## core/
순수 로직 모듈 (UI 독립)
- `cache/`: 썸네일 캐시 로직
- `db/`: SQLite 스키마/쿼리/저장
- `extract/`: EXIF/stealth payload 추출
- `normalize/`: 태그 정규화
- `match/`: 태그 매칭
- `preset/`: 템플릿 스키마/입출력
- `adapters/`: 외부 포맷(NAIS/Legacy) 변환
- `utils/`: 공통 유틸(파일명/집합 연산/진행도)
- `runner/`: 병렬 실행

## server/
FastAPI 서버 (현재 사용)
- `main.py`: HTTP/WebSocket 서버, 작업 라우팅
- `context.py`: 작업 컨텍스트

## sidecar/
작업 핸들러 (서버에서 호출)
- `jobs.py`: 작업 디스패처
- `handlers/`: scan/search/rename/move 등 작업 구현
- `emitter.py`: JSON Lines 출력
- `job_manager.py`: 작업 상태 관리

## viewer-ui/
Svelte 프론트엔드 (현재 사용)
- `src/components/`: 화면 컴포넌트 (MovePanel, SearchPanel 등)
- `src/lib/`: 유틸, API 호출
- Vite로 빌드 → `dist/`

## ui/
Tauri UI (레거시, 미사용)
- Svelte/Tauri 기반
- `src-tauri/`: Rust 백엔드

## gui/
Tkinter 프로토타입 (레거시)
- 백업/참고용으로 유지

## db/
- `schema.sql`: SQLite 스키마 정의

## debug/
수동 테스트용 스크립트
- `db_smoke.py`: DB 스키마 검증
- `perf_db.py`: DB 성능 측정
- `perf_extract.py`: 태그 추출 성능
- `inspect_exif.py`: EXIF 확인
- `thumb_cache.py`: 썸네일 캐시 테스트
- `ipc_echo.py`: IPC 에코 테스트

## tests/
자동 테스트 (pytest/unittest 호환)
- `conftest.py`: 공유 fixtures
- `test_*.py`: 테스트 모듈
