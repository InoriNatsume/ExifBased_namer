# NAI 태그 분류기 설계 (Korean)

## 목표
- NAI EXIF/stealth 태그를 기반으로 이미지 분류/이름 변경/폴더 이동을 수행한다.
- 사용자가 정의한 프리셋(변수/값/태그조합)을 편집하고, NAIS 포맷을 임포트/익스포트한다.
- 코어 로직과 UI를 분리해, Tkinter 프로토타입과 향후 Tauri UI 모두에서 재사용 가능하게 한다.

## 설계 원칙
- 책임 분리: 코어/어댑터/입출력/UI를 분리하고 역할 경계를 명확히 한다.
- 모듈화: 재사용 가능한 단위로 쪼개고, 교체 가능한 구조를 유지한다.
- 테스트/디버깅 중시: 자동 테스트와 수동 디버깅 도구를 분리하고 기록 가능한 로그를 남긴다.

## 범위
- 태그 매칭은 AND 조건만 사용한다.
- 임포트: NAIS 및 레거시/SDStudio 계열 포맷 지원.
- 익스포트: NAIS(ScenePreset) 포맷만 지원.
- 검색/분류/이름변경은 대량 파일(10만+)을 고려한다.

## 용어 정의
- 프리셋: 변수/값/태그조합의 전체 묶음(JSON으로 저장 가능).
- 변수: 분류 기준의 이름(예: character, emotion). 키/이름 분리 없이 이름만 사용.
- 값: 변수 내 항목(예: angry_1, sad_1).
- 태그 조합: 값이 요구하는 필수 태그 묶음(AND 기준).
- 드라이런: 실제 파일 변경 없이 결과만 계산.
- @@@ 제거: 중복되는 파일명을 가진 서로 다른 이미지들이 존재할 경우에 @@@숫자로 구별하는데, 중복처리가 완료되었을 때 파일명 끝의 @@@숫자를 제거.
- OK/UNKNOWN/CONFLICT: 매칭 결과 상태(일치 1개/0개/2개 이상).

## 코어 데이터 모델 (Pydantic v2)
- Preset
  - name: str | None
  - variables: list[Variable]
- Variable
  - name: str
  - values: list[VariableValue]
- VariableValue
  - name: str
  - tags: list[str] (정규화됨)
  - tag_set: frozenset[str] (파생, 매칭/검증용)
- MatchResult
  - variables: list[VariableMatch]

검증 규칙
- 동일 태그 조합 금지
- 부분집합 관계 금지 (A ⊂ B)
- 태그 비어있는 값은 편집 허용, 매칭에서 제외, NAIS 익스포트 시 에러

## 태그 추출/정규화
- stealth PNG(alpha) + EXIF(Comment/Description 등)에서 payload 추출
- Comment/Description은 JSON 문자열/딕셔너리 모두 처리
- 정규화: 가중치 제거, 괄호 처리, 쉼표 분리
- prompt_tags + char_prompt_tags 사용
- 네거티브 포함 여부는 옵션

## 분류/검색/이름변경/폴더분류 플로우
1) 이미지에서 태그 추출
2) 변수별 AND 매칭
3) 결과 상태 결정 (OK/UNKNOWN/CONFLICT)
4) 파일명 변경 또는 폴더 이동 수행 (드라이런 가능)

## 임포트/익스포트
- NAIS import:
  - scene.name -> VariableValue.name
  - scene.scenePrompt -> tags
- Legacy/SDStudio import:
  - 프롬프트 조합을 값으로 변환
- NAIS export:
  - Variable -> ScenePreset
  - VariableValue -> Scene

임포트 시 동작
- 팝업에서 “덮어쓰기/추가” 선택
  - 예=덮어쓰기, 아니오=추가
- 이후 중복/부분집합 검사 수행
- 충돌 발견 시 자동 제외 여부 선택

## 공통 태그 제거(교집합/차집합)
- 변수 내 모든 값의 태그 교집합을 공통 태그로 계산
- 각 값의 태그에서 공통 태그를 제거하여 고유 태그만 유지
- 공통 태그는 변수별 캐시로 저장(메모리) 및 별도 보기/복사 지원
- 집합 연산 로직은 core.tag_sets로 분리

## 값 이름 일괄 변경
- 앞/뒤 단어 추가
- 단어 바꾸기
- 단어 삭제
- 빈 이름이 생기면 중단

## 성능/진행 표시
- 멀티프로세스 처리
- 진행도/ETA 계산
- 결과 리스트는 제한 수 표시 (UI 성능 고려)

## 현재 UI (Tkinter 프로토타입)
- 편집/검색/파일명 변경/폴더 분류 탭
- 결과 목록 스크롤 + 미리보기 + 필터
- 문제 로그 파일 출력

## 향후 UI (Tauri + React/Svelte)
권장: Tauri + Python sidecar + JSON Lines IPC
- 포트 없이 로컬 IPC
- Python 코어 그대로 사용
- UI는 웹 스택으로 교체

### React vs Svelte 비교 (요약)
React
- 장점: 생태계/라이브러리 풍부, 인력 수급 용이
- 단점: 상태/보일러플레이트가 많아짐
Svelte
- 장점: 코드량 적고 UI 반응성이 좋음, 러닝커브 완만
- 단점: 생태계가 React보다 작음

권장
- 혼자 유지 + 빠른 개발: Svelte
- 팀 확장 + 라이브러리 의존: React

선택
- UI 프레임워크는 Svelte로 진행

## 로깅
- Python logging (INFO)
- 작업 시작/종료, 처리 수, 상태별 카운트, 예외 로그

## 테스트 포인트
- Comment 파싱: dict/string/missing
- NAI 버전별 payload 차이
- 태그 정규화(가중치/괄호/파이프)
- 중복/부분집합 검증
- AND 매칭
- 공통 태그 제거

## 테스트 구성
- 자동 테스트: tests/ 아래 unittest (pytest 이식 가능 구조)
- 수동 디버깅: debug/inspect_exif.py (자동 테스트에 포함하지 않음)

## 테스트 포인트 ↔ 테스트 파일 매핑
- Comment 파싱: `tests/test_extract.py`
- 태그 정규화/병합: `tests/test_normalize.py`
- 중복/부분집합 검증: `tests/test_schema.py`
- 매칭(OK/UNKNOWN/CONFLICT, AND): `tests/test_match.py`
- 공통 태그 제거/차집합/충돌 감지: `tests/test_tag_sets.py`
- NAIS 익스포트 기본 검증: `tests/test_import_export.py`

## 프로젝트 구조(요약)
- `core/`: 태그 추출/정규화/매칭/프리셋/집합 연산 등 순수 로직
- `gui/`: Tkinter 프로토타입 UI (추후 제거 예정, 레거시로 유지)
- `nais_builder/`: 폴더 기반 NAIS 생성 모듈 (독립 사용 가능)
- `tests/`: unittest 기반 자동 테스트
- `debug/`: 수동 디버깅 스크립트

## core/ 재구성안(초안)
- `core/extract/`: EXIF/stealth payload 추출
- `core/normalize/`: 태그 정규화/프롬프트 결합
- `core/match/`: 매칭/분류 로직
- `core/preset/`: 프리셋 스키마/입출력
- `core/adapters/`: 외부 포맷 임포트/익스포트(NAIS/Legacy)
- `core/utils/`: 공통 유틸(파일명/집합 연산/진행도)
