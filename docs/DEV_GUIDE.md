# 개발자 가이드

## 구조 개요
- `core/`: 태그 추출/정규화/매칭/캐시 등 순수 로직
- `server/`: FastAPI 서버 (HTTP/WebSocket)
- `sidecar/`: 작업 핸들러 (jobs.py, handlers/)
- `viewer-ui/`: Svelte 프론트엔드
- `ui/`: Tauri UI (레거시)
- `debug/`: 수동 디버깅 스크립트

## 빌드 및 실행

### 개발 모드
```powershell
# 1. 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 2. 서버 실행
python -m server.main

# 3. 브라우저에서 열기
# http://localhost:8000
```

### 프로덕션 빌드
```powershell
# PowerShell 빌드 스크립트
.\build.ps1

# 또는 npm 빌드 건너뛰기
.\build.ps1 -SkipNpm

# 결과: dist/nai-classifier-server.exe (32.5MB)
```

### 빌드 파일
- `build.spec`: PyInstaller 설정
- `build.ps1`: Windows 빌드 스크립트

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

## 테스트 실행

### pytest (권장)
```powershell
# 전체 테스트
pytest tests/ -v

# 특정 파일
pytest tests/test_db.py -v

# 특정 테스트
pytest tests/test_match.py::MatchTests::test_match_conflict -v
```

### unittest (대체)
```powershell
python tests/run_tests.py
```

### GitHub Actions
- Python 3.11/3.12/3.13 매트릭스
- Windows + Ubuntu 테스트
- PR/Push 시 자동 실행

## 디버깅 도구
- `debug/inspect_exif.py`: EXIF/stealth 확인
- `debug/ipc_echo.py`: IPC 에코 테스트
- `debug/db_smoke.py`: DB 스키마 확인
- `debug/thumb_cache.py`: 썸네일 캐시 테스트
- `debug/perf_extract.py`: EXIF 추출/정규화 성능 측정
- `debug/perf_db.py`: DB 검색 성능 측정
  - 옵션: `--repeat`, `--explain`, `--selectivity`
