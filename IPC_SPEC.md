# IPC 메시지 스펙 (초안)

## 공통 규칙
- JSON Lines: 한 줄에 JSON 1개
- `id`: 작업 ID
- `type`: 메시지 유형
- `op`: 작업 종류(`run` 메시지에서만 사용)
- `payload`: 작업 입력(`run` 메시지에서만 사용)
- `version`: 프로토콜 버전(옵션, 기본 1)
- 환경 변수 `NAI_DB_PATH`로 DB 경로 지정(기본 `data/app.sqlite`)

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
- `version`(int): 프로토콜 버전(옵션)

### cancel
```json
{"id":"job-1","type":"cancel"}
```
필드
- `id`(str): 취소할 작업 ID
- `type` = `cancel`
- `version`(int): 프로토콜 버전(옵션)

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
{"id":"job-1","type":"result","status":"OK","source":"...","target":"...","message":null,"preview":"..."}
```
필드
- `preview`(str): 썸네일 캐시 경로(옵션)

### done
```json
{"id":"job-1","type":"done","processed":50000,"errors":3,"skipped":200,"cancelled":false}
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
  "thumbs": true,
  "thumb_size": 256,
  "thumb_quality": 85,
  "thumb_cache_dir": "C:\\cache\\thumbs",
  "thumb_max_files": 5000,
  "thumb_max_bytes": 2147483648,
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
- `incremental`(bool): 변경된 파일만 재처리
- `workers`(int): 병렬 워커 수(미지정 시 CPU 기반 자동)
- `thumbs`(bool): 썸네일 캐시 사용 여부
- `thumb_size`/`thumb_quality`: 썸네일 크기/품질(옵션)
- `thumb_cache_dir`: 캐시 폴더(옵션, 미지정 시 `cache/thumbs`)
- `thumb_max_files`/`thumb_max_bytes`: 캐시 정리 정책(옵션)

### search
설명: DB 또는 폴더 기준 태그 AND 검색.
payload
```json
{
  "tags": "tag1, tag2",
  "folder": "C:\\images",
  "include_negative": false,
  "progress_step": 200,
  "thumbs": true,
  "thumb_size": 256,
  "thumb_quality": 85,
  "thumb_cache_dir": "C:\\cache\\thumbs",
  "thumb_max_files": 5000,
  "thumb_max_bytes": 2147483648,
  "limit": 2000,
  "offset": 0
}
```
필드
- `tags`(str): 필수 태그(쉼표 구분)
- `folder`(str): 지정 시 폴더 직접 검색
- `include_negative`(bool): 네거티브 태그 포함 여부(폴더 검색 시)
- `progress_step`(int): 진행도 업데이트 주기(폴더 검색 시)
- `thumbs`(bool): 썸네일 캐시 사용 여부
- `limit`/`offset`: DB 검색 페이징

### rename
설명: 템플릿 기반 파일명 변경.
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
  "thumbs": true,
  "thumb_size": 256,
  "thumb_quality": 85,
  "thumb_cache_dir": "C:\\cache\\thumbs",
  "thumb_max_files": 5000,
  "thumb_max_bytes": 2147483648,
  "resume_mode": false,
  "resume_path": "C:\\images\\.nai_resume_rename.txt",
  "checkpoint_step": 200,
  "variables": [
    {"name": "character", "values": [{"name": "yuina", "tags": ["tag1"]}]}
  ]
}
```
필드
- `folder`(str): 대상 폴더
- `order`(list|str): 템플릿에 넣을 변수 순서
- `template`(str): 파일명 형식
- `prefix_mode`(bool): 템플릿을 접두사로 붙이기
- `dry_run`(bool): 실제 변경 없이 결과만 계산
- `include_negative`(bool): 네거티브 태그 포함 여부
- `progress_step`(int): 진행도 업데이트 주기
- `resume_mode`(bool): 재개 모드(기존 체크포인트 읽기)
- `resume_path`(str): 체크포인트 파일 경로(미지정 시 기본 경로)
- `checkpoint_step`(int): 체크포인트 기록 플러시 주기
- `thumbs`(bool): 썸네일 캐시 사용 여부
- `variables`(list): 변수/값/태그 목록
- `variable_specs`(list): 변수 스펙(있으면 우선 사용)

체크포인트 정책
- 체크포인트 파일은 항상 기록됨
- `resume_mode=true`일 때 기존 체크포인트를 읽어 스킵 처리
- 작업 완료 시 체크포인트 파일 자동 삭제
- 중단/강제 종료 시 파일 유지

### move
설명: 변수 기준 폴더 분류. 단일 변수 또는 계층별 분류 지원.
payload
```json
{
  "folder": "C:\\images",
  "variable_name": "emotion",
  "variable_tree": ["character", "emotion"],
  "template": "[value]",
  "target_root": "C:\\target",
  "dry_run": true,
  "include_negative": false,
  "progress_step": 200,
  "thumbs": true,
  "thumb_size": 256,
  "thumb_quality": 85,
  "thumb_cache_dir": "C:\\cache\\thumbs",
  "thumb_max_files": 5000,
  "thumb_max_bytes": 2147483648,
  "resume_mode": false,
  "resume_path": "C:\\images\\.nai_resume_move.txt",
  "checkpoint_step": 200,
  "variables": []
}
```
필드
- `variable_name`(str): 단일 변수 분류 시 사용
- `variable_tree`(list): 계층별 분류 시 변수 순서 (예: `["character", "emotion"]`)
  - 지정 시 `variable_name` 무시
  - 1층만 매칭되면 PARTIAL 상태로 1층 폴더에 분류
- `template`(str): 폴더명 형식 (`[value]` 등)
- `target_root`(str): 대상 루트 폴더
- `dry_run`(bool): 실제 이동 없이 결과만 계산
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

### build_nais
설명: 폴더 분석으로 프리셋 값 생성.
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
설명: 템플릿 JSON 불러오기.
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
설명: 템플릿 JSON 저장.
payload
```json
{
  "path": "C:\\path\\template.json",
  "preset": {"name": "", "variables": []}
}
```

### preset_import
설명: SDSTUDIO/NAIS 프리셋 값 불러오기(변수 1개 단위).
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

### resume_clear
설명: 재개 체크포인트 파일 삭제.
payload
```json
{
  "folder": "C:\\images",
  "kind": "rename"
}
```
done payload
```json
{
  "path": "C:\\images\\.nai_resume_rename.txt",
  "removed": true
}
```
필드
- `kind`: `rename` 또는 `move`
- `path`: 직접 경로 지정 시 사용

## 에러/취소 규칙
- JSON 파싱 실패 시 `error` 응답
- `cancel` 수신 시 진행 중인 작업은 안전 종료

## Windows CMD 참고
- 경로에 `\`가 있으면 `\\`로 이스케이프 필요

### template_db_list
설명: 템플릿 목록 조회(DB).
payload
```json
{}
```
done payload
```json
{
  "templates": [{"id": 1, "name": "main", "updated_at": "..." }]
}
```

### template_db_get
설명: 템플릿 단건 조회(DB).
payload
```json
{
  "id": 1,
  "name": "main"
}
```
done payload
```json
{
  "id": 1,
  "name": "main",
  "payload": {"name": "main", "variables": []},
  "updated_at": "..."
}
```

### template_db_save
설명: 템플릿 저장(DB).
payload
```json
{
  "name": "main",
  "template": {"name": "main", "variables": []}
}
```
done payload
```json
{
  "id": 1,
  "name": "main"
}
```

### template_db_delete
설명: 템플릿 삭제(DB).
payload
```json
{
  "name": "main"
}
```
done payload
```json
{
  "name": "main"
}
```

### preset_db_list
설명: 프리셋 목록 조회(DB).
payload
```json
{
  "source_kind": "nais",
  "variable_name": "emotion"
}
```
done payload
```json
{
  "presets": [
    {
      "id": 10,
      "name": "emo-pack",
      "source_kind": "nais",
      "variable_name": "emotion",
      "updated_at": "..."
    }
  ]
}
```

### preset_db_get
설명: 프리셋 단건 조회(DB).
payload
```json
{
  "id": 10
}
```
done payload
```json
{
  "id": 10,
  "name": "emo-pack",
  "source_kind": "nais",
  "variable_name": "emotion",
  "payload": {"name": "emo-pack", "source_kind": "nais", "variable_name": "emotion", "values": []},
  "updated_at": "..."
}
```

### preset_db_save
설명: 프리셋 저장(DB).
payload
```json
{
  "preset": {
    "name": "emo-pack",
    "source_kind": "nais",
    "variable_name": "emotion",
    "values": [{"name": "angry", "tags": ["tag1"]}]
  }
}
```
done payload
```json
{
  "id": 10,
  "name": "emo-pack"
}
```

### preset_db_delete
설명: 프리셋 삭제(DB).
payload
```json
{
  "id": 10
}
```
done payload
```json
{
  "id": 10
}
```
