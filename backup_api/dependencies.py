from functools import lru_cache
from .config import load_config

@lru_cache()
def get_settings():
    config = load_config()
    global_config = config.get("global", {})
    restore_mode = global_config.get("restore_mode", False)

    return {
        "restore_mode": restore_mode,
        "max_parallel_jobs": global_config.get("max_parallel_jobs", 1)
    }
