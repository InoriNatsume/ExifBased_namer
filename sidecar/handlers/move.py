import shutil
from pathlib import Path
from typing import TextIO

from core.runner import match_variable_specs
from core.utils import ensure_unique_name, iter_image_files, render_template, sanitize_filename

from ..job_manager import JobContext
from .common import load_tags, load_variable_specs
from .thumbs import apply_thumb_policy, ensure_preview


def handle_move(ctx: JobContext, conn) -> None:
    folder = ctx.payload.get("folder")
    # 계층별 분류: variable_tree가 배열이면 여러 변수 순서대로 폴더 위계 생성
    variable_tree = ctx.payload.get("variable_tree") or []
    variable_name = ctx.payload.get("variable_name") or ""
    template = ctx.payload.get("template") or "[value]"
    target_root = ctx.payload.get("target_root") or ""
    dry_run = bool(ctx.payload.get("dry_run", True))
    include_negative = bool(ctx.payload.get("include_negative", False))
    progress_step = max(1, int(ctx.payload.get("progress_step") or 200))
    resume_mode = bool(ctx.payload.get("resume_mode", False))
    resume_path = ctx.payload.get("resume_path")
    checkpoint_step = max(1, int(ctx.payload.get("checkpoint_step") or 200))

    # variable_tree가 있으면 그것을 사용, 없으면 단일 variable_name을 리스트로
    if isinstance(variable_tree, list) and len(variable_tree) > 0:
        var_list = variable_tree
    elif variable_name:
        var_list = [variable_name]
    else:
        var_list = []

    if not folder:
        ctx.error(ctx.job_id, "folder is required")
        return
    if not var_list:
        ctx.error(ctx.job_id, "variable_tree or variable_name is required")
        return
    if not target_root:
        ctx.error(ctx.job_id, "target_root is required")
        return

    variable_specs = load_variable_specs(ctx.payload)
    if not variable_specs:
        ctx.error(ctx.job_id, "variable_specs or variables is required")
        return
    spec_names = {spec.get("name") for spec in variable_specs}
    for vn in var_list:
        if vn not in spec_names:
            ctx.error(ctx.job_id, f"unknown variable in tree: {vn}")
            return

    image_paths = iter_image_files(folder)
    total = len(image_paths)
    processed = 0
    errors = 0
    skipped = 0
    resume_written = 0
    resume_file: TextIO | None = None
    resume_done: set[str] = set()
    reserved_map: dict[str, set[str]] = {}

    if not resume_path:
        resume_path = str(Path(folder) / ".nai_resume_move.txt")
    resume_file_path = Path(str(resume_path))
    resume_file_path.parent.mkdir(parents=True, exist_ok=True)
    if resume_mode and resume_file_path.exists():
        try:
            with resume_file_path.open("r", encoding="utf-8") as handle:
                resume_done = {line.strip() for line in handle if line.strip()}
        except Exception:
            resume_done = set()
    else:
        resume_file_path.write_text("", encoding="utf-8")
    resume_file = resume_file_path.open("a", encoding="utf-8")

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "progress",
            "processed": processed,
            "total": total,
            "errors": errors,
            "skipped": skipped,
        }
    )

    cancelled = False
    try:
        for path in image_paths:
            if path in resume_done:
                skipped += 1
                processed += 1
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                            "skipped": skipped,
                        }
                    )
                continue
            if ctx.is_cancelled():
                cancelled = True
                ctx.emit({"id": ctx.job_id, "type": "done", "cancelled": True})
                return
            try:
                tags = load_tags(conn, path, include_negative)
                matches = match_variable_specs(variable_specs, tags)
            except Exception as exc:
                errors += 1
                processed += 1
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": "ERROR",
                        "source": path,
                        "message": str(exc),
                    }
                )
                if resume_file:
                    resume_file.write(f"{path}\n")
                    resume_written += 1
                    if resume_written % checkpoint_step == 0:
                        resume_file.flush()
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                            "skipped": skipped,
                        }
                    )
                continue

            # 계층별 분류: var_list의 각 변수에 대해 폴더 경로 조합
            # OK인 변수들까지만 폴더 경로를 만들고, 나머지는 실패해도 부분 분류
            folder_parts = []
            last_fail_status = None  # 마지막으로 실패한 상태
            for vn in var_list:
                match = matches.get(vn, {})
                st = match.get("status") or "UNKNOWN"
                if st == "OK":
                    val = match.get("values", [""])[0]
                    part = render_template(template, {"value": val})
                    part = sanitize_filename(part)
                    if part:
                        folder_parts.append(part)
                    else:
                        last_fail_status = "ERROR"
                        break
                else:
                    # OK가 아닌 경우 여기서 멈추고, 지금까지 모은 folder_parts로 분류
                    last_fail_status = st
                    break

            # 전체 OK면 OK, 부분 분류면 PARTIAL, 아무것도 못하면 원래 상태
            if len(folder_parts) == len(var_list):
                overall_status = "OK"
            elif len(folder_parts) > 0:
                overall_status = "PARTIAL"  # 부분 분류됨
            else:
                overall_status = last_fail_status or "UNKNOWN"

            # 폴더 경로가 하나도 없으면 분류 불가 (UNKNOWN, CONFLICT 등)
            if not folder_parts:
                processed += 1
                preview = ensure_preview(ctx.payload, path)
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "result",
                        "status": overall_status,
                        "source": path,
                        "target": None,
                        "message": f"1단계 변수부터 매칭 실패",
                        "preview": preview,
                    }
                )
                if resume_file:
                    resume_file.write(f"{path}\n")
                    resume_written += 1
                    if resume_written % checkpoint_step == 0:
                        resume_file.flush()
                if processed % progress_step == 0 or processed == total:
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "progress",
                            "processed": processed,
                            "total": total,
                            "errors": errors,
                            "skipped": skipped,
                        }
                    )
                continue

            # 계층 폴더 경로 생성
            target_folder = Path(target_root)
            for part in folder_parts:
                target_folder = target_folder / part
            target_folder = str(target_folder)
            # 결과에 표시할 분류 폴더 (target_root 상대경로)
            classified_folder = "/".join(folder_parts)
            if target_folder not in reserved_map:
                try:
                    names = {
                        p.name.lower()
                        for p in Path(target_folder).glob("*")
                        if p.is_file()
                    }
                except FileNotFoundError:
                    names = set()
                reserved_map[target_folder] = names

            reserved = reserved_map[target_folder]
            ext = Path(path).suffix
            base = Path(path).stem
            new_name = ensure_unique_name(target_folder, base, ext, reserved)
            target = str(Path(target_folder) / new_name)

            if not dry_run:
                Path(target_folder).mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(path, target)
                except Exception as exc:
                    errors += 1
                    processed += 1
                    ctx.emit(
                        {
                            "id": ctx.job_id,
                            "type": "result",
                            "status": "ERROR",
                            "source": path,
                            "message": str(exc),
                        }
                    )
                    if resume_file:
                        resume_file.write(f"{path}\n")
                        resume_written += 1
                        if resume_written % checkpoint_step == 0:
                            resume_file.flush()
                    if processed % progress_step == 0 or processed == total:
                        ctx.emit(
                            {
                                "id": ctx.job_id,
                                "type": "progress",
                                "processed": processed,
                                "total": total,
                                "errors": errors,
                                "skipped": skipped,
                            }
                        )
                    continue

            processed += 1
            preview_source = path if dry_run else target
            preview = ensure_preview(ctx.payload, preview_source)
            ctx.emit(
                {
                    "id": ctx.job_id,
                    "type": "result",
                    "status": "OK",
                    "source": path,
                    "target": target,
                    "folder": classified_folder,  # 분류된 폴더 경로 (탐색용)
                    "message": None,
                    "preview": preview,
                }
            )
            if resume_file:
                final_path = path if dry_run else target
                resume_file.write(f"{final_path}\n")
                resume_written += 1
                if resume_written % checkpoint_step == 0:
                    resume_file.flush()
            if processed % progress_step == 0 or processed == total:
                ctx.emit(
                    {
                        "id": ctx.job_id,
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "errors": errors,
                        "skipped": skipped,
                    }
                )
    finally:
        if resume_file:
            resume_file.flush()
            resume_file.close()
        if not cancelled:
            resume_file_path.unlink(missing_ok=True)

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "processed": processed,
            "errors": errors,
            "skipped": skipped,
        }
    )
    apply_thumb_policy(ctx.payload)
