"""Shared product graph schema helpers.

This module defines the default user-visible ASIP graph contract. Raw fact
storage may keep richer implementation details, but product output must project
through these node kinds and relation names.
"""

from __future__ import annotations

import re
from typing import List, Optional


ALLOWED_PRODUCT_NODE_KINDS = {"function", "register", "doc"}

ALLOWED_PRODUCT_RELATIONS = {
    "calls",
    "configures",
    "contains",
    "depends_on",
    "documents",
    "maps_base",
    "reads",
    "relates_to",
    "resets",
    "sets_field",
    "writes",
}

PROVENANCE_ONLY_RELATIONS = {
    "appears_in_code",
    "appears_in_doc",
    "appears_in_pdf",
    "defined_in",
    "has_field",
    "wraps",
}

_LOCAL_OR_PROVENANCE_TOKENS = {
    "callbacks",
    "data",
    "funcs",
    "gc",
    "init_func",
    "init_funcs",
    "ip_version",
    "local",
    "ops",
    "reg",
    "ret",
    "ring",
    "tmp",
    "value",
}

_WRAPPER_TOKENS = {
    "AMDGV_WREG32",
    "GPU_REGISTER",
    "REG_SET_FIELD",
    "RREG32",
    "SOC15_REG_OFFSET",
    "WREG32",
    "WREG32_SOC15",
}

# Default register inventory – matches the resolver profile default.
# These are the standard AMD register prefixes used when no resolver
# profile provides an override.
_DEFAULT_REGISTER_PREFIXES: List[str] = ["reg", "mm", "smn"]
_DEFAULT_REJECT_TOKENS: List[str] = ["tmp", "value", "adapt", "data", "ops", "funcs", "ret", "reg", "local", "ring", "init_func"]


def is_register_symbol(symbol: str) -> bool:
    """Return True when *symbol* looks like a plausible register name
    under the default ASIP register inventory rules."""
    raw = symbol.strip()
    if not raw or raw.lower() in {t.lower() for t in _DEFAULT_REJECT_TOKENS}:
        return False
    for prefix in _DEFAULT_REGISTER_PREFIXES:
        if raw.startswith(prefix) and len(raw) > len(prefix) and raw[len(prefix)].isupper():
            return True
    return False


def is_product_node_kind(kind: str) -> bool:
    return kind.strip().lower() in ALLOWED_PRODUCT_NODE_KINDS


def normalize_product_relation(relation: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9]+", "_", relation.lower()).strip("_")
    if normalized in {"read", "reads", "field_get", "field_read", "field_mask", "field_shift"}:
        return "reads"
    if normalized in {"write", "writes", "field_write", "field_value"}:
        return "writes"
    if normalized in {
        "field_set",
        "sets_field",
        "set_field",
        "sets_field_value",
        "reg_set_field",
        "read_modify_write",
        "read_modify_writes",
    }:
        return "sets_field"
    if normalized in {"maps_base", "map_base", "address", "offset", "maps_offset"}:
        return "maps_base"
    if normalized in {"calls", "call"}:
        return "calls"
    if normalized in {"contains", "contains_box"}:
        return "contains"
    if normalized in {"documents", "documents_register", "documented_by", "section_mentions", "explains"}:
        return "documents"
    if normalized in {"depends_on", "requires"}:
        return "depends_on"
    if normalized in {"configures", "programs"}:
        return "configures"
    if normalized in {"resets", "reset"}:
        return "resets"
    if normalized in PROVENANCE_ONLY_RELATIONS:
        return None
    return "relates_to"


def product_endpoint_kind(endpoint: str) -> Optional[str]:
    value = endpoint.strip()
    if not value:
        return None
    upper = value.upper()
    lower = value.lower()
    if upper in _WRAPPER_TOKENS or lower in _LOCAL_OR_PROVENANCE_TOKENS:
        return None
    if lower.startswith(("data_", "local_", "ret_", "tmp_", "value_")):
        return None
    if upper.startswith(("ENABLE_", "DISABLE_")):
        return None
    if ":" in value:
        prefix = value.split(":", 1)[0].lower()
        if prefix in {"doc", "doc_box", "doc_section", "pdf_section"}:
            return "doc"
        if prefix in {"function", "register"}:
            return prefix
        return None
    if "#" in value and re.search(r"\.(?:md|rst|txt|pdf)#", lower):
        return "doc"
    if is_register_symbol(value):
        return "register"
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", value) and any(part in upper for part in ("CNTL", "CTRL", "STATUS", "BASE", "RESET")):
        return "register"
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) and "_" in value and not value.isupper():
        return "function"
    return None
