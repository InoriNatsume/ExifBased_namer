from core.db.query import get_template, list_templates
from core.db.storage import delete_template, upsert_template
from core.preset import Preset

from ..job_manager import JobContext


def handle_template_db_list(ctx: JobContext, conn) -> None:
    templates = list_templates(conn)
    ctx.emit({"id": ctx.job_id, "type": "done", "payload": {"templates": templates}})


def handle_template_db_get(ctx: JobContext, conn) -> None:
    template_id = ctx.payload.get("id")
    name = ctx.payload.get("name")
    template = get_template(conn, template_id=template_id, name=name)
    if not template:
        ctx.error(ctx.job_id, "template not found")
        return
    ctx.emit({"id": ctx.job_id, "type": "done", "payload": template})


def handle_template_db_save(ctx: JobContext, conn) -> None:
    raw = ctx.payload.get("template")
    name = ctx.payload.get("name")
    if not isinstance(raw, dict):
        ctx.error(ctx.job_id, "template is required")
        return
    template = Preset.model_validate(raw)
    template_name = template.name or name
    if not template_name:
        ctx.error(ctx.job_id, "template name is required")
        return
    payload = template.model_dump()
    payload["name"] = template_name
    template_id = upsert_template(conn, template_name, payload)
    conn.commit()
    ctx.emit(
        {
            "id": ctx.job_id,
            "type": "done",
            "payload": {"id": template_id, "name": template_name},
        }
    )


def handle_template_db_delete(ctx: JobContext, conn) -> None:
    name = ctx.payload.get("name")
    if not name:
        ctx.error(ctx.job_id, "name is required")
        return
    ok = delete_template(conn, name)
    if not ok:
        ctx.error(ctx.job_id, "template not found")
        return
    conn.commit()
    ctx.emit({"id": ctx.job_id, "type": "done", "payload": {"name": name}})
