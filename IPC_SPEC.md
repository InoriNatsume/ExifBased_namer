# IPC 메시지 스키마 (초안)

## 공통 규칙
- JSON Lines: 한 줄에 JSON 1개
- `id`: 작업 ID
- `type`: 메시지 유형
- `op`: 작업 종류(`run` 메시지에서 사용)
- `payload`: 작업 입력(`run` 메시지에서 사용)
- 환경 변수: `NAI_DB_PATH`로 DB 경로 지정 가능(기본 `data/app.sqlite`)

## 요청 메시지
### run
```json
{"id":"job-1","type":"run","op":"scan","payload":{...}}
```
필드
- `id`(str): 작업 ID
- `type` = `run`
- `op`: 작업 종류
- `payload`: 작업 입력

### cancel
```json
{"id":"job-1","type":"cancel"}
```
필드
- `id`(str): 취소할 작업 ID
- `type` = `cancel`

## 응답 메시지
### ack
```json
{"id":"job-1","type":"ack","op":"scan"}
```

### progress
```json
{"id":"job-1","type":"progress","processed":1200,"total":50000,"errors":3,"skipped":200}
```

### result
```json
{"id":"job-1","type":"result","status":"OK","source":"...","target":"...","message":null}
```

### done
```json
{"id":"job-1","type":"done","processed":50000,"errors":3,"skipped":200}
```

### error
```json
{"id":"job-1","type":"error","message":"..."}
```

### log
```json
{"id":"job-1","type":"log","message":"elapsed=12.34s"}
```

## 작업 종류 (op)
### scan
설명: 폴더 내 이미지 태그 추출 후 DB 저장.
payload
```json
{
  "folder": "C:\\images",
  "include_negative": false,
  "progress_step": 200,
  "commit_step": 200,
  "incremental": false,
  "workers": 6
}
```
필드
- `folder`(str): 스캔 대상 폴더
- `include_negative`(bool): 네거티브 태그 포함 여부
- `progress_step`(int): 진행도 업데이트 주기
- `commit_step`(int): DB 커밋 주기
- `incremental`(bool): 변경된 파일만 처리
- `workers`(int): 병렬 워커 수(미지정 시 CPU 기준 자동)

### search
설명: DB 또는 폴더 기준으로 태그 AND 검색.
payload
```json
{
  "tags": "tag1, tag2",
  "folder": "C:\\images",
  "include_negative": false,
  "progress_step": 200,
  "limit": 2000,
  "offset": 0
}
```
필드
- `folder`(str): 지정 시 폴더 내 파일을 순회하며 검색
- `include_negative`(bool): 네거티브 태그 포함 여부(폴더 검색 시 사용)
- `progress_step`(int): 진행도 업데이트 주기(폴더 검색 시 사용)

### rename
설명: 템플릿에 따라 파일명 변경.
payload
```json
{
  "folder": "C:\\images",
  "order": ["character", "emotion"],
  "template": "[character]_[emotion]",
  "prefix_mode": false,
  "dry_run": true,
  "include_negative": false,
  "progress_step": 200,
  "variables": [
    {"name": "character", "values": [{"name": "yuina", "tags": ["tag1"]}]}
  ]
}
```
필드
- `folder`(str): 대상 폴더
- `order`(list|str): 템플릿에 쓸 변수 순서
- `template`(str): 출력 템플릿
- `prefix_mode`(bool): 템플릿을 접두사로 붙이기
- `dry_run`(bool): 실제 변경 없이 결과만 계산
- `include_negative`(bool): 네거티브 태그 포함 여부(태그 추출 fallback 시 사용)
- `progress_step`(int): 진행도 업데이트 주기
- `variables`(list): 변수/값/태그 목록
- `variable_specs`(list): `build_variable_specs` 결과(있으면 `variables` 대신 사용)

### move
설명: 단일 변수 값을 기준으로 폴더 분류.
payload
```json
{
  "folder": "C:\\images",
  "variable_name": "emotion",
  "template": "[value]",
  "target_root": "C:\\target",
  "dry_run": true,
  "include_negative": false,
  "progress_step": 200,
  "variables": []
}
```

### strip_suffix
설명: 파일명 끝의 `@@@숫자` 제거.
payload
```json
{
  "folder": "C:\\images",
  "dry_run": true,
  "progress_step": 200
}
```

### db_stats
설명: DB 기본 통계 조회.
payload
```json
{}
```

## 에러/취소 규칙
- JSON 파싱 실패 시 `error`로 응답.
- `cancel` 수신 시 진행 중인 작업은 안전 종료.

## Windows CMD 참고
- 경로에 `\`가 있는 경우 `\\`로 이스케이프 필요.

### build_nais
Description: build preset data from a folder (variable 1개) and return values for preset import.
payload
```json
{
  "folder": "C:\\images",
  "include_negative": false,
  "progress_step": 200
}
```
done payload
```json
{
  "variable_name": "folder_name",
  "values": [{"name": "value1", "tags": ["tag1", "tag2"]}],
  "common_tags": ["tagA", "tagB"]
}
```

### preset_load
Description: load template json (전체 템플릿) into app.
payload
```json
{
  "path": "C:\\path\\template.json"
}
```

done payload
```json
{
  "preset": {"name": "", "variables": []},
  "path": "C:\\path\\template.json"
}
```

### preset_save
Description: save template json (전체 템플릿) to disk.
payload
```json
{
  "path": "C:\\path\\template.json",
  "preset": {"name": "", "variables": []}
}
```

### preset_import
Description: import SDSTUDIO/NAIS preset values (변수 1개 단위).
payload
```json
{
  "path": "C:\\path\\template.json"
}
```

done payload
```json
{
  "variable_name": "optional",
  "values": [{"name": "value1", "tags": ["tag1"]}]
}
```
