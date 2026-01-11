import json

from core.adapters.legacy import import_legacy_payload
from core.adapters.nais import import_nais_payload
from core.preset import Preset, load_preset, save_preset

from ..job_manager import JobContext


def handle_preset_load(ctx: JobContext, conn) -> None:
    path = ctx.payload.get("path")
    if not path:
        ctx.error(ctx.job_id, "path is required")
        return
    preset = load_preset(path)
    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "payload": {
                "preset": preset.model_dump(),
                "path": path,
            },
        }
    )


def handle_preset_save(ctx: JobContext, conn) -> None:
    path = ctx.payload.get("path")
    raw = ctx.payload.get("preset")
    if not path:
        ctx.error(ctx.job_id, "path is required")
        return
    if not isinstance(raw, dict):
        ctx.error(ctx.job_id, "preset is required")
        return
    preset = Preset.model_validate(raw)
    save_preset(path, preset)
    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "payload": {"path": path},
        }
    )


def handle_preset_import(ctx: JobContext, conn) -> None:
    path = ctx.payload.get("path")
    if not path:
        ctx.error(ctx.job_id, "path is required")
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        ctx.error(ctx.job_id, f"failed to read json: {exc}")
        return

    try:
        if isinstance(payload, dict) and isinstance(payload.get("scenes"), list):
            variable_name, values = import_nais_payload(payload)
        else:
            variable_name, values = import_legacy_payload(payload)
    except Exception as exc:
        ctx.error(ctx.job_id, f"unsupported preset format: {exc}")
        return

    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "payload": {
                "variable_name": variable_name,
                "values": [value.model_dump() for value in values],
            },
        }
    )
