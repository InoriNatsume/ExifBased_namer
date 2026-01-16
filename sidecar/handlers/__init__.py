from .build import handle_build_nais
from .db import handle_db_stats
from .move import handle_move
from .preset import handle_preset_import, handle_preset_load, handle_preset_save
from .preset_db import (
    handle_preset_db_delete,
    handle_preset_db_get,
    handle_preset_db_list,
    handle_preset_db_save,
)
from .rename import handle_rename
from .resume import handle_resume_clear
from .scan import handle_scan
from .search import handle_search
from .strip import handle_strip_suffix
from .template_db import (
    handle_template_db_delete,
    handle_template_db_get,
    handle_template_db_list,
    handle_template_db_save,
)

__all__ = [
    "handle_build_nais",
    "handle_db_stats",
    "handle_move",
    "handle_preset_import",
    "handle_preset_load",
    "handle_preset_save",
    "handle_preset_db_delete",
    "handle_preset_db_get",
    "handle_preset_db_list",
    "handle_preset_db_save",
    "handle_rename",
    "handle_resume_clear",
    "handle_scan",
    "handle_search",
    "handle_strip_suffix",
    "handle_template_db_delete",
    "handle_template_db_get",
    "handle_template_db_list",
    "handle_template_db_save",
]
