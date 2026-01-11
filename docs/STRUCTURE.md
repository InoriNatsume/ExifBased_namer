# 폴더 구조

## core/
- `cache/`: 썸네일 캐시 로직
- `extract/`: EXIF/stealth payload 추출
- `normalize/`: 태그 정규화
- `match/`: 태그 매칭
- `preset/`: 템플릿 스키마/입출력
- `adapters/`: 외부 포맷(NAIS/Legacy) 변환
- `utils/`: 공통 유틸(파일명/집합 연산/진행도)
- `runner/`: 병렬 실행

## sidecar/
- IPC 루프 및 작업 핸들러
- `handlers/`: scan/search/rename/move 등 작업 구현

## ui/
- Svelte/Tauri UI
- `src/components/`: 화면 컴포넌트
- `src/lib/`: IPC, 모델, 스토어

## debug/
- 수동 테스트용 스크립트

## tests/
- unittest 기반 자동 테스트
