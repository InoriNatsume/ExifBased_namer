# Svelte + Tauri UI (초안)

## 목표
- Python sidecar와 IPC(JSON Lines) 연동을 위한 UI 골격.
- 최종 UI로 이전하기 전에 레이아웃/상태/이벤트 흐름을 검증.

## 실행 전제
- Node.js, Rust, Tauri CLI(v2) 필요.
- 로컬에서만 사용.

## 개발 실행(예시)
- 프론트: `npm install` 후 `npm run dev`
- Tauri: `npx tauri dev` (또는 전역 설치 시 `cargo tauri dev`)

## IPC 연결 참고
- Tauri가 프로젝트 루트를 못 찾으면 `NAI_ROOT` 환경변수를 설정.
- `src/lib/ipc.ts`에서 `sidecar-message` 이벤트를 수신.
