from core.db.query import get_tags_for_path
from core.extract import extract_tags_from_image
from core.runner import build_variable_specs


def load_variable_specs(payload: dict) -> list[dict]:
    specs = payload.get("variable_specs")
    if isinstance(specs, list):
        return specs
    variables = payload.get("variables")
    if isinstance(variables, list):
        return build_variable_specs(variables)
    return []


def load_tags(
    conn,
    path: str,
    include_negative: bool,
) -> list[str]:
    tags = get_tags_for_path(conn, path, include_negative=include_negative)
    if tags is not None:
        return tags
    return extract_tags_from_image(path, include_negative)
