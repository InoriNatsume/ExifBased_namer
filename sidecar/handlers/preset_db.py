from core.db.query import get_preset, list_presets
from core.db.storage import delete_preset, save_preset
from core.preset import VariableValue

from ..job_manager import JobContext


def handle_preset_db_list(ctx: JobContext, conn) -> None:
    source_kind = ctx.payload.get("source_kind")
    variable_name = ctx.payload.get("variable_name")
    presets = list_presets(conn, source_kind=source_kind, variable_name=variable_name)
    ctx.emit({"id": ctx.job_id, "type": "done", "payload": {"presets": presets}})


def handle_preset_db_get(ctx: JobContext, conn) -> None:
    preset_id = ctx.payload.get("id")
    if preset_id is None:
        ctx.error(ctx.job_id, "id is required")
        return
    preset = get_preset(conn, preset_id=int(preset_id))
    if not preset:
        ctx.error(ctx.job_id, "preset not found")
        return
    ctx.emit({"id": ctx.job_id, "type": "done", "payload": preset})


def handle_preset_db_save(ctx: JobContext, conn) -> None:
    raw = ctx.payload.get("preset")
    if not isinstance(raw, dict):
        ctx.error(ctx.job_id, "preset is required")
        return
    name = raw.get("name") or ctx.payload.get("name")
    source_kind = raw.get("source_kind") or ctx.payload.get("source_kind")
    variable_name = raw.get("variable_name") or ctx.payload.get("variable_name")
    values = raw.get("values")
    preset_id = raw.get("id")

    if not name or not source_kind or not variable_name:
        ctx.error(ctx.job_id, "name/source_kind/variable_name are required")
        return
    if not isinstance(values, list):
        ctx.error(ctx.job_id, "values is required")
        return

    validated = [VariableValue.model_validate(item).model_dump() for item in values]
    payload = {
        "name": name,
        "source_kind": source_kind,
        "variable_name": variable_name,
        "values": validated,
    }
    new_id = save_preset(
        conn,
        name=name,
        source_kind=source_kind,
        variable_name=variable_name,
        payload=payload,
        preset_id=int(preset_id) if preset_id is not None else None,
    )
    conn.commit()
    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "payload": {"id": new_id, "name": name},
        }
    )


def handle_preset_db_delete(ctx: JobContext, conn) -> None:
    preset_id = ctx.payload.get("id")
    if preset_id is None:
        ctx.error(ctx.job_id, "id is required")
        return
    ok = delete_preset(conn, int(preset_id))
    if not ok:
        ctx.error(ctx.job_id, "preset not found")
        return
    conn.commit()
    ctx.emit({"id": ctx.job_id, "type": "done", "payload": {"id": int(preset_id)}})
