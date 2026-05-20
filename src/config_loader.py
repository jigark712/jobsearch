from functools import lru_cache
from typing import Any

import yaml

from src.paths import CONFIG_DIR


@lru_cache(maxsize=1)
def preferences() -> dict[str, Any]:
    with (CONFIG_DIR / "preferences.yaml").open() as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def companies() -> dict[str, Any]:
    with (CONFIG_DIR / "companies.yaml").open() as f:
        return yaml.safe_load(f)
