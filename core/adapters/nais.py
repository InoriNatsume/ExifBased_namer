from __future__ import annotations

import time
from uuid import uuid4

from ..normalize import split_novelai_tags
from ..preset.schema import Variable, VariableValue


def import_nais_payload(payload: dict) -> tuple[str | None, list[VariableValue]]:
    if not isinstance(payload, dict):
        raise ValueError("NAIS payload must be a dict")

    scenes = payload.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("NAIS payload missing scenes list")

    values: list[VariableValue] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        name = str(scene.get("name") or "Untitled")
        prompt = scene.get("scenePrompt") or ""
        if not isinstance(prompt, str):
            prompt = str(prompt)
        tags = split_novelai_tags(prompt)
        values.append(VariableValue(name=name, tags=tags))

    return payload.get("name"), values


def export_variable_to_nais(variable: Variable) -> dict:
    created_at = int(time.time() * 1000)
    scenes = []
    for value in variable.values:
        if not value.tags:
            raise ValueError(f"empty tags are not allowed: '{value.name}'")
        scenes.append(
            {
                "id": uuid4().hex,
                "name": value.name,
                "scenePrompt": ", ".join(value.tags),
                "queueCount": 0,
                "images": [],
                "createdAt": created_at,
            }
        )

    return {
        "id": uuid4().hex,
        "name": variable.name,
        "scenes": scenes,
        "createdAt": created_at,
    }
