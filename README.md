# NAI Tag Classifier

[![Tests](https://github.com/InoriNatsume/ExifBased_namer/actions/workflows/tests.yml/badge.svg)](https://github.com/InoriNatsume/ExifBased_namer/actions/workflows/tests.yml)

NAI 이미지의 EXIF/stealth 태그를 기반으로 검색, 파일명 변경, 폴더 분류를 수행하는 도구입니다.

## 기능

- **검색**: 태그 AND 조건으로 이미지 검색
- **파일명 변경**: 템플릿 기반 일괄 파일명 변경
- **폴더 분류**: 계층별 변수 기준 폴더 분류 (부분 분류 지원)
- **DB 스캔**: 대량 파일 인덱싱 및 증분 스캔
- **프리셋 관리**: NAIS/SDStudio 프리셋 임포트/익스포트

## 빠른 시작

### 실행 파일 사용 (권장)

```powershell
# exe 파일 실행
.\nai-classifier-server.exe

# 브라우저에서 열기
# http://localhost:8000
```

### 개발 모드

```powershell
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 프론트엔드 빌드
cd viewer-ui
npm install
npm run build
cd ..

# 3. 서버 실행
python -m server.main
```

## 빌드

```powershell
# PowerShell 빌드 스크립트
.\build.ps1

# 결과: dist/nai-classifier-server.exe (32.5MB)
```

## 프로젝트 구조

```
core/           # 태그 추출/정규화/매칭/캐시 순수 로직
server/         # FastAPI 서버 (HTTP/WebSocket)
sidecar/        # 작업 핸들러
viewer-ui/      # Svelte 프론트엔드
db/             # SQLite 스키마
debug/          # 디버깅 도구
tests/          # 자동 테스트
docs/           # 문서
```

## 문서

- [DESIGN.md](DESIGN.md) - 설계 문서
- [PLAN.md](PLAN.md) - 개발 계획
- [IPC_SPEC.md](IPC_SPEC.md) - IPC 메시지 스펙
- [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md) - 개발자 가이드
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - 사용자 가이드
- [docs/STRUCTURE.md](docs/STRUCTURE.md) - 폴더 구조

## 테스트

```powershell
# pytest (권장)
pytest tests/ -v

# unittest
python tests/run_tests.py
```

26개 테스트 (DB, 태그 추출/정규화/매칭, 스키마 검증 등)

## 기술 스택

- **백엔드**: Python, FastAPI, SQLite, Pillow
- **프론트엔드**: Svelte, TypeScript, Vite
- **패키징**: PyInstaller

## 라이선스

Private
