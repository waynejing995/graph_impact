"""Config-driven symbol resolver profiles for ASIP evidence extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class WrapperRule:
    symbol_arg: int
    access: str = "reference"


@dataclass(frozen=True)
class ResolverProfile:
    id: str
    language: str
    wrappers: Dict[str, WrapperRule] = field(default_factory=dict)
    symbol_prefixes: List[str] = field(default_factory=list)
    context_vars: List[str] = field(default_factory=list)
    python_extractors: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedSymbol:
    profile_id: str
    wrapper: str
    symbol: str
    symbol_argument: int
    access: str


def load_resolver_profiles(profile_dir: Path) -> Dict[str, ResolverProfile]:
    profiles: Dict[str, ResolverProfile] = {}
    for path in sorted(profile_dir.glob("*.yaml")):
        profile = load_resolver_profile(path)
        profiles[profile.id] = profile
    return profiles


def load_resolver_profile(path: Path) -> ResolverProfile:
    data = _parse_profile_yaml(path.read_text(encoding="utf-8"))
    profile_id = str(data.get("id", path.stem))
    language = str(data.get("language", "cpp"))
    wrappers = {
        name: WrapperRule(symbol_arg=int(rule.get("symbol_arg", 0)), access=str(rule.get("access", "reference")))
        for name, rule in data.get("wrappers", {}).items()
    }
    return ResolverProfile(
        id=profile_id,
        language=language,
        wrappers=wrappers,
        symbol_prefixes=list(data.get("symbol_prefixes", [])),
        context_vars=list(data.get("context_vars", [])),
        python_extractors=list(data.get("python_extractors", [])),
    )


def resolve_cpp_register_call(source: str, profile: ResolverProfile) -> Optional[ResolvedSymbol]:
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)\)", source, flags=re.DOTALL):
        wrapper = match.group(1)
        rule = profile.wrappers.get(wrapper)
        if not rule:
            continue
        args = _split_call_args(match.group(2))
        if rule.symbol_arg >= len(args):
            continue
        symbol = _canonical_symbol(args[rule.symbol_arg], profile.symbol_prefixes)
        return ResolvedSymbol(
            profile_id=profile.id,
            wrapper=wrapper,
            symbol=symbol,
            symbol_argument=rule.symbol_arg,
            access=rule.access,
        )
    return None


def resolve_python_symbol(source: str, profile: ResolverProfile) -> Optional[ResolvedSymbol]:
    for extractor in profile.python_extractors:
        match = re.search(rf"\b{re.escape(extractor)}\s*\(\s*['\"]([^'\"]+)['\"]", source)
        if match:
            return ResolvedSymbol(
                profile_id=profile.id,
                wrapper=extractor,
                symbol=match.group(1),
                symbol_argument=0,
                access="reference",
            )
    return None


def _split_call_args(args: str) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for char in args:
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth > 0:
            depth -= 1
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _canonical_symbol(raw: str, prefixes: Iterable[str]) -> str:
    symbol = raw.strip().strip("&*")
    symbol = symbol.split("->")[-1] if "->" in symbol and "[" not in symbol else symbol
    symbol = re.sub(r"[^A-Za-z0-9_].*$", "", symbol)
    for prefix in sorted(prefixes, key=len, reverse=True):
        if symbol.startswith(prefix) and len(symbol) > len(prefix) and symbol[len(prefix)].isupper():
            symbol = symbol[len(prefix) :]
            break
    return symbol


def _parse_profile_yaml(text: str) -> Dict[str, object]:
    data: Dict[str, object] = {"wrappers": {}}
    section: Optional[str] = None
    active_wrapper: Optional[str] = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0:
            active_wrapper = None
            key, value = _split_key_value(line)
            if value == "":
                section = key
                continue
            section = None
            data[key] = _parse_scalar(value)
            continue
        if section == "wrappers" and indent == 2:
            active_wrapper = line.rstrip(":")
            wrappers = data.setdefault("wrappers", {})
            assert isinstance(wrappers, dict)
            wrappers[active_wrapper] = {}
            continue
        if section == "wrappers" and indent == 4 and active_wrapper:
            key, value = _split_key_value(line)
            wrappers = data["wrappers"]
            assert isinstance(wrappers, dict)
            wrapper_rule = wrappers[active_wrapper]
            assert isinstance(wrapper_rule, dict)
            wrapper_rule[key] = _parse_scalar(value)

    return data


def _split_key_value(line: str) -> tuple[str, str]:
    key, _, value = line.partition(":")
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> object:
    if value == "{}":
        return {}
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    if value.isdigit():
        return int(value)
    if value in {"true", "false"}:
        return value == "true"
    return value.strip("'\"")
