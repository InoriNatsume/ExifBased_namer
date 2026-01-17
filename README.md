# NAI Classifier

[![Tests](https://github.com/InoriNatsume/ExifBased_namer/actions/workflows/tests.yml/badge.svg)](https://github.com/InoriNatsume/ExifBased_namer/actions/workflows/tests.yml)

NovelAI 이미지 태그 추출/검색/파일명 변경/폴더 분류 도구.

---

## 목차

- [빠른 시작](#빠른-시작)
- [사용 가이드](#사용-가이드)
- [개발자 가이드](#개발자-가이드)
- [API 스펙](#api-스펙)
- [아키텍처 및 설계](#아키텍처-및-설계)
- [프로젝트 구조](#프로젝트-구조)

---

## 빠른 시작

### 실행 파일 사용 (권장)

```powershell
# 빌드된 exe 실행
.\dist\nai-classifier-server.exe

# 브라우저에서 접속
http://localhost:8000
```

### 개발 모드

```powershell
# 의존성 설치
pip install -r requirements.txt

# FastAPI 서버 실행
python -m server.main

# 브라우저에서 접속
http://localhost:8000
```

### 빌드

```powershell
# PowerShell
.\build.ps1

# 또는 batch
build.bat
```

결과물: `dist/nai-classifier-server.exe` (약 32.5MB)

---

## 사용 가이드

### 용어 정리

| 용어 | 설명 |
|------|------|
| **템플릿** | 여러 변수의 집합. 파일명/폴더 분류 기준 정의 |
| **프리셋** | 템플릿 또는 변수/값 집합을 저장한 JSON |
| **변수 (variable)** | 분류 기준 (예: character, emotion) |
| **값 (value)** | 변수에 속하는 항목 (예: yuina, happy) |
| **태그 조합** | 값에 매핑된 태그 목록 (예: `["happy", "smile"]`) |
| **드라이런 (dry_run)** | 실제 파일 변경 없이 결과만 미리 확인 |
| **재개 모드 (resume_mode)** | 중단된 작업을 이어서 처리 |

### 주요 기능

#### 1. DB 스캔
폴더 내 이미지의 태그를 추출하여 DB에 저장.
- 증분 스캔: 변경된 파일만 재처리
- 썸네일 캐시 자동 생성

#### 2. 태그 검색
DB 또는 폴더 기준 태그 AND 검색.
- 쉼표로 구분된 태그 입력
- 결과 목록 + 썸네일 미리보기

#### 3. 파일명 변경 (Rename)
템플릿 기반 파일명 일괄 변경.
- 예: `[character]_[emotion].png`
- 드라이런으로 미리 확인 권장

#### 4. 폴더 분류 (Move)
변수 기준 폴더로 파일 이동.
- **단일 변수**: 하나의 변수 기준 분류
- **계층별 분류**: 여러 변수로 `character/emotion/` 형태
- **부분 분류 (PARTIAL)**: 1층만 매칭되면 1층 폴더로 이동

#### 5. @@@ 제거 (Strip Suffix)
파일명 끝의 `@@@숫자` 제거.

### 결과 상태 코드

| 상태 | 설명 |
|------|------|
| **OK** | 정상 매칭 (전체 변수 매칭) |
| **PARTIAL** | 부분 매칭 (일부 변수만 매칭) |
| **UNKNOWN** | 매칭 없음 |
| **CONFLICT** | 여러 값이 매칭됨 (충돌) |
| **ERROR** | 처리 오류 |
| **SKIP** | 재개 모드에서 스킵됨 |

### 재개 모드

rename/move 작업 중단 시 체크포인트 파일 생성:
- `.nai_resume_rename.txt`
- `.nai_resume_move.txt`

재개 모드 활성화 시 완료된 항목 스킵.
작업 완료 시 체크포인트 파일 자동 삭제.

---

## 개발자 가이드

### 빌드 및 실행

```powershell
# 의존성 설치
pip install -r requirements.txt

# FastAPI 서버 실행
python -m server.main

# 또는 디버그 모드
python -m server.main --debug
```

### 테스트 실행

```powershell
# pytest (권장)
pytest tests/ -v

# 단일 파일
pytest tests/test_match.py -v

# unittest 호환
python -m unittest discover -s tests
```

테스트 현황: 26개 테스트, Python 3.11/3.12/3.13 지원.

### 디버그 도구 (debug/)

| 스크립트 | 용도 |
|----------|------|
| `inspect_exif.py` | EXIF/스텔스 태그 수동 확인 |
| `ipc_echo.py` | IPC 메시지 송수신 테스트 |
| `db_smoke.py` | DB 스키마 생성/쿼리 검증 |
| `thumb_cache.py` | 썸네일 캐시 생성/정리 테스트 |
| `perf_extract.py` | EXIF 추출/정규화 성능 측정 |
| `perf_db.py` | DB 검색 성능 측정 |

### 썸네일 캐시

```powershell
# 환경 변수로 캐시 경로 지정
$env:NAI_THUMB_DIR = "C:\cache\thumbs"

# 캐시 정책 설정
$env:NAI_THUMB_MAX_FILES = "5000"
$env:NAI_THUMB_MAX_BYTES = "2147483648"  # 2GB
```

### DB 경로

```powershell
$env:NAI_DB_PATH = "C:\path\to\app.sqlite"
```

기본값: `data/app.sqlite`

---

## API 스펙

### 아키텍처
- **서버**: FastAPI (Python)
- **통신**: HTTP REST + WebSocket
- **포트**: 8000 (기본)

### 엔드포인트

#### 작업 생성
```http
POST /api/job
Content-Type: application/json

{"op": "scan", "payload": {...}}
```
응답:
```json
{"job_id": "scan-a1b2c3d4", "status": "created"}
```

#### 작업 진행률/결과 (WebSocket)
```
WS /api/job/{job_id}/ws
```

#### 작업 취소
```http
POST /api/job/{job_id}/cancel
```

#### 썸네일
```http
GET /api/thumb?path={encoded_path}
```

#### DB 통계
```http
GET /api/db/stats
```

### WebSocket 메시지 타입

#### progress
```json
{"type": "progress", "processed": 1200, "total": 50000, "errors": 3, "skipped": 200}
```

#### result
```json
{"type": "result", "status": "OK", "source": "...", "target": "...", "preview": "..."}
```

#### done
```json
{"id": "job-1", "type": "done", "processed": 50000, "errors": 3, "cancelled": false}
```

#### error
```json
{"id": "job-1", "type": "error", "message": "..."}
```

### 작업 종류 (op)

| op | 설명 |
|----|------|
| `scan` | 폴더 태그 추출 → DB 저장 |
| `search` | 태그 AND 검색 |
| `rename` | 템플릿 기반 파일명 변경 |
| `move` | 변수 기준 폴더 분류 |
| `strip_suffix` | `@@@숫자` 제거 |
| `build_nais` | 폴더 분석으로 프리셋 생성 |
| `preset_load` | 템플릿 JSON 불러오기 |
| `preset_save` | 템플릿 JSON 저장 |
| `preset_import` | SDSTUDIO/NAIS 프리셋 임포트 |
| `resume_clear` | 재개 체크포인트 삭제 |
| `template_db_*` | DB 템플릿 CRUD |
| `preset_db_*` | DB 프리셋 CRUD |

### 주요 페이로드 예시

#### scan
```json
{
  "folder": "C:\\images",
  "include_negative": false,
  "thumbs": true,
  "incremental": false,
  "workers": 6
}
```

#### search
```json
{
  "tags": "tag1, tag2",
  "folder": "C:\\images",
  "limit": 2000
}
```

#### rename
```json
{
  "folder": "C:\\images",
  "template": "[character]_[emotion]",
  "dry_run": true,
  "resume_mode": false,
  "variables": [
    {"name": "character", "values": [{"name": "yuina", "tags": ["tag1"]}]}
  ]
}
```

#### move
```json
{
  "folder": "C:\\images",
  "variable_tree": ["character", "emotion"],
  "target_root": "C:\\target",
  "dry_run": true
}
```
- `variable_tree`: 계층별 분류 시 변수 순서
- 1층만 매칭되면 PARTIAL 상태로 1층 폴더에 분류

---

## 아키텍처 및 설계

### 설계 원칙
- **UI/코어 분리**: 태그 추출/매칭 로직은 `core/`에 독립
- **DB 중심**: 태그는 DB에 캐시, 검색/매칭은 DB 우선
- **스트리밍**: WebSocket으로 실시간 진행률/결과 전송
- **재개 지원**: 중단된 작업 이어서 처리

### 데이터 모델

#### Template
```python
{
  "name": "main",
  "variables": [Variable, ...]
}
```

#### Variable
```python
{
  "name": "character",
  "values": [VariableValue, ...]
}
```

#### VariableValue
```python
{
  "name": "yuina",
  "tags": ["tag1", "tag2", ...]
}
```

#### MatchResult
```python
{
  "status": "OK",       # OK/PARTIAL/UNKNOWN/CONFLICT
  "value": "yuina",     # 매칭된 값
  "matches": [...]      # 매칭된 태그 목록
}
```

### 태그 추출/정규화

1. **EXIF 추출**: `PIL.ExifTags` + stealth PNG
2. **NAI 버전별 처리**: v1 (Description), v2 (Comment), v3 (Software)
3. **정규화**: 가중치 `(tag:1.2)` → `tag`, 괄호/밑줄 정규화, 공백 트림

### DB 스키마 (SQLite)

```sql
-- 이미지
images(id, path, mtime, size, hash, tags_json)

-- 태그 (행 단위)
tags(image_id, tag)

-- 매칭 결과
matches(image_id, variable, status, values)

-- 템플릿/프리셋
templates(id, name, payload, updated_at)
presets(id, name, source_kind, variable_name, payload, updated_at)
```

### 임포트/익스포트

| 포맷 | 설명 |
|------|------|
| **NAIS** | NAI wildcard 형식 (`{folder\|tags}`) |
| **SDSTUDIO** | SD Studio 확장 JSON |
| **폴더 분석** | 폴더명 → 값, 태그 추출 |

---

## 프로젝트 구조

```
├── core/                 # 핵심 로직 (UI 독립)
│   ├── adapters/         # NAIS/Legacy 포맷 어댑터
│   ├── cache/            # 썸네일 캐시
│   ├── db/               # SQLite 스키마/쿼리
│   ├── extract/          # EXIF/stealth 태그 추출
│   ├── match/            # 매칭/분류 로직
│   ├── normalize/        # 태그 정규화
│   ├── preset/           # 템플릿 스키마/IO
│   ├── runner/           # 병렬 처리 워커
│   └── utils/            # 공통 유틸
├── server/               # FastAPI 서버
│   └── main.py           # 엔트리포인트
├── sidecar/              # JSON Lines IPC (레거시)
│   ├── handlers/         # 작업별 핸들러
│   ├── job_manager.py    # 작업 큐 관리
│   └── main.py           # sidecar 엔트리
├── viewer-ui/            # Svelte 프론트엔드
│   └── src/              # Svelte 컴포넌트
├── gui/                  # Tkinter UI (레거시)
├── ui/                   # Tauri UI (미사용)
├── db/                   # DB 스키마 SQL
├── debug/                # 디버그 스크립트
├── tests/                # 자동 테스트
├── data/                 # 런타임 데이터 (DB 등)
├── cache/                # 썸네일 캐시
├── build.spec            # PyInstaller 설정
├── build.ps1             # 빌드 스크립트
├── requirements.txt      # Python 의존성
└── PLAN.md               # TODO/Changelog
```

---

## 라이선스

gpl 3.0

## Credit


UI

- https://arca.live/b/characterai/155936654

- https://arca.live/b/characterai/159771658


포맷

- https://github.com/sunanakgo/NAIS2

- SDStudio 

