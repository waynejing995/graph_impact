"""Shared graph entity filters."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .resolver_profiles import load_resolver_profiles


_BUILTIN_RESOLVER_OPERATORS = {
    "REG_SET_FIELD",
    "REG_GET_FIELD",
    "amdgv_wait_for_register",
    "gpu_register",
    "register_ref",
    "field_ref",
    "ip_ref",
    "asic_ref",
    "schema_ref",
    "config_key",
}


def is_resolver_wrapper_name(symbol: str) -> bool:
    value = symbol.strip()
    if not value:
        return False
    return (
        value.startswith(("RREG", "WREG", "SOC15_REG_", "amdgv_wreg", "amdgv_rreg"))
        or value.startswith("REG_FIELD_")
        or value in _BUILTIN_RESOLVER_OPERATORS
        or value in _configured_resolver_operator_names()
    )


def is_graph_entity_endpoint(symbol: str) -> bool:
    return bool(symbol.strip()) and not is_resolver_wrapper_name(symbol)


@lru_cache(maxsize=1)
def _configured_resolver_operator_names() -> frozenset[str]:
    resolver_dir = Path(__file__).resolve().parents[4] / "configs" / "resolvers"
    if not resolver_dir.exists():
        return frozenset()
    try:
        profiles = load_resolver_profiles(resolver_dir)
    except Exception:
        return frozenset()
    operators = set()
    for profile in profiles.values():
        operators.update(profile.wrappers.keys())
        operators.update(profile.python_extractors)
    return frozenset(operators)
