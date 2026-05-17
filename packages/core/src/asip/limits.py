"""Config-backed workbench limits.

All product-facing graph, retrieval, and semantic generation budgets should
come from this file-backed layer. CLI flags and API params are overrides, not
hidden defaults.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_WORKBENCH_LIMITS_PATH = REPO_ROOT / "configs" / "workbench-limits.json"


@dataclass(frozen=True)
class WorkbenchLimits:
    path: Path
    data: Mapping[str, Any] = field(default_factory=dict)

    def int_value(self, section: str, key: str, *, minimum: Optional[int] = None) -> Optional[int]:
        value = self.value(section, key)
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        if minimum is not None:
            return max(minimum, parsed)
        return parsed

    def float_value(self, section: str, key: str, *, minimum: Optional[float] = None, maximum: Optional[float] = None) -> Optional[float]:
        value = self.value(section, key)
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def value(self, section: str, key: str) -> Any:
        section_data = self.data.get(section, {}) if isinstance(self.data, Mapping) else {}
        if section == "graph" and not section_data and isinstance(self.data, Mapping):
            section_data = self.data.get("globalGraph", {})
        if not isinstance(section_data, Mapping):
            return None
        for candidate in (key, _snake_to_camel(key)):
            if candidate in section_data:
                return section_data[candidate]
        return None


def load_workbench_limits(path: Optional[Path] = None) -> WorkbenchLimits:
    limits_path = (path or DEFAULT_WORKBENCH_LIMITS_PATH).expanduser()
    if not limits_path.exists():
        return WorkbenchLimits(path=limits_path, data={})
    data = json.loads(limits_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"workbench limits must be a JSON object: {limits_path}")
    return WorkbenchLimits(path=limits_path, data=data)


def _snake_to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])
