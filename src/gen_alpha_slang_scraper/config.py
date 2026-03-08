from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from gen_alpha_slang_scraper.utils import read_json


DEFAULT_CONFIG_PATH = Path("configs/default.json")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str | None = None) -> dict[str, Any]:
    base = read_json(DEFAULT_CONFIG_PATH)
    if not config_path:
        return base
    override = read_json(config_path)
    return deep_merge(base, override)

