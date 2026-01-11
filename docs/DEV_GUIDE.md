# 개발자 가이드

## 구조 개요
- `core/`: 태그 추출/정규화/매칭/캐시 등 순수 로직
- `sidecar/`: IPC 서버, 작업 핸들러
- `ui/`: Svelte/Tauri UI
- `debug/`: 수동 디버깅 스크립트

## IPC
- JSON Lines 기반
- 문서: `IPC_SPEC.md`
- 프로토콜 버전: `version` 필드(기본 1)

## 썸네일 캐시
- 기본 경로: `cache/thumbs`
- 관련 모듈: `core/cache/thumbs.py`
- 생성: `ensure_thumbnail`
- 정리: `prune_cache`

### 환경 변수
- `NAI_CACHE_DIR`: 캐시 폴더
- `NAI_CACHE_MAX_FILES`: 최대 파일 수
- `NAI_CACHE_MAX_BYTES`: 최대 바이트
- `NAI_CACHE_THUMB_SIZE`: 썸네일 크기
- `NAI_CACHE_THUMB_QUALITY`: JPEG 품질

## 재개 체크포인트
- 파일명 변경: `.nai_resume_rename.txt`
- 폴더 분류: `.nai_resume_move.txt`
- 작업 완료 시 자동 삭제, 중단 시 유지

## 디버깅 도구
- `debug/inspect_exif.py`: EXIF/stealth 확인
- `debug/ipc_echo.py`: IPC 에코 테스트
- `debug/db_smoke.py`: DB 스키마 확인
- `debug/thumb_cache.py`: 썸네일 캐시 테스트
