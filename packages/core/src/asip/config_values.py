"""Helpers for late-bound provider configuration values."""

from __future__ import annotations

import os
import re
from typing import Mapping


_ENV_PLACEHOLDER = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")
_ENV_DIRECT = re.compile(r"env:([A-Za-z_][A-Za-z0-9_]*)")


def expand_env_placeholders(value: str, *, field: str = "value") -> str:
    """Expand explicit environment placeholders without logging secret values."""
    direct = _ENV_DIRECT.fullmatch(value.strip())
    if direct:
        return _required_env(direct.group(1), field)

    def replace(match: re.Match[str]) -> str:
        return _required_env(match.group(1), field)

    return _ENV_PLACEHOLDER.sub(replace, value)


def expand_extra_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        str(key): expand_env_placeholders(str(value), field=f"header {key}")
        for key, value in headers.items()
    }


def _required_env(name: str, field: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"{field} references unset environment variable {name}")
    return value
