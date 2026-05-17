"""Config-driven symbol resolver profiles for ASIP evidence extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class WrapperRule:
    symbol_arg: int = 0
    access: str = "reference"
    symbol_args: tuple[int, ...] = ()

    def argument_indexes(self) -> tuple[int, ...]:
        return self.symbol_args or (self.symbol_arg,)


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
    field_symbol: str = ""


def load_resolver_profiles(profile_dir: Path) -> Dict[str, ResolverProfile]:
    profiles: Dict[str, ResolverProfile] = {}
    for path in sorted(profile_dir.glob("*.yaml")):
        profile = load_resolver_profile(path)
        profiles[profile.id] = profile
    return profiles


def load_resolver_profile(path: Path) -> ResolverProfile:
    data = _parse_profile_yaml(path.read_text(encoding="utf-8"))
    return resolver_profile_from_config(data, fallback_id=path.stem)


def resolver_profile_from_config(
    config: Mapping[str, object],
    fallback_id: str = "",
    fallback_language: str = "cpp",
    fallback_wrappers: Sequence[str] = (),
    fallback_strategy: str = "reference",
) -> ResolverProfile:
    profile_id = str(config.get("id", fallback_id))
    language = str(config.get("language", fallback_language))
    wrappers_data = config.get("wrappers", {})
    wrappers = _wrapper_rules_from_config(wrappers_data if isinstance(wrappers_data, Mapping) else {})
    if not wrappers and fallback_wrappers:
        wrappers = {wrapper: WrapperRule(symbol_arg=0, access=fallback_strategy) for wrapper in fallback_wrappers}
    return ResolverProfile(
        id=profile_id,
        language=language,
        wrappers=wrappers,
        symbol_prefixes=_string_list(config.get("symbol_prefixes", [])),
        context_vars=_string_list(config.get("context_vars", [])),
        python_extractors=_string_list(
            config.get("python_extractors", fallback_wrappers if language == "python" else [])
        ),
    )


def resolver_profile_to_config(profile: ResolverProfile) -> Dict[str, object]:
    wrappers: Dict[str, Dict[str, object]] = {}
    for name, rule in profile.wrappers.items():
        wrapper_config: Dict[str, object] = {"symbol_arg": rule.symbol_arg, "access": rule.access}
        if rule.symbol_args:
            wrapper_config["symbol_args"] = list(rule.symbol_args)
        wrappers[name] = wrapper_config
    return {
        "id": profile.id,
        "language": profile.language,
        "context_vars": list(profile.context_vars),
        "symbol_prefixes": list(profile.symbol_prefixes),
        "python_extractors": list(profile.python_extractors),
        "wrappers": wrappers,
    }


def resolve_cpp_register_call(source: str, profile: ResolverProfile) -> Optional[ResolvedSymbol]:
    resolved = resolve_cpp_register_calls(source, profile)
    return resolved[0] if resolved else None


def resolve_cpp_register_calls(source: str, profile: ResolverProfile) -> List[ResolvedSymbol]:
    resolved_symbols: List[ResolvedSymbol] = []
    seen: set[tuple[str, str, int, str, str]] = set()
    for wrapper, call_args in _iter_configured_cpp_calls(source, profile):
        rule = profile.wrappers.get(wrapper)
        if not rule:
            continue
        args = _split_call_args(call_args)
        if _is_field_access(rule.access) and len(rule.argument_indexes()) >= 2:
            register_arg, field_arg = rule.argument_indexes()[:2]
            if register_arg >= len(args) or field_arg >= len(args):
                continue
            register_symbols = _symbols_for_argument(args[register_arg], profile)
            field_symbols = _symbols_for_argument(args[field_arg], profile)
            for register_symbol in register_symbols:
                for field_symbol in field_symbols or [""]:
                    if not register_symbol:
                        continue
                    key = (wrapper, register_symbol, register_arg, rule.access, field_symbol)
                    if key in seen:
                        continue
                    seen.add(key)
                    resolved_symbols.append(
                        ResolvedSymbol(
                            profile_id=profile.id,
                            wrapper=wrapper,
                            symbol=register_symbol,
                            symbol_argument=register_arg,
                            access=rule.access,
                            field_symbol=field_symbol,
                        )
                    )
            continue
        for symbol_arg in rule.argument_indexes():
            if symbol_arg < 0 or symbol_arg >= len(args):
                continue
            symbols = _symbols_for_argument(args[symbol_arg], profile)
            for symbol in symbols:
                if not symbol:
                    continue
                key = (wrapper, symbol, symbol_arg, rule.access, "")
                if key in seen:
                    continue
                seen.add(key)
                resolved_symbols.append(
                    ResolvedSymbol(
                        profile_id=profile.id,
                        wrapper=wrapper,
                        symbol=symbol,
                        symbol_argument=symbol_arg,
                        access=rule.access,
                    )
                )
    return resolved_symbols


def _is_field_access(access: str) -> bool:
    return access in {
        "field_get",
        "field_mask",
        "field_read",
        "field_set",
        "field_shift",
        "field_value",
        "field_write",
    }


def _wrapper_rules_from_config(wrappers_data: Mapping[str, object]) -> Dict[str, WrapperRule]:
    wrappers: Dict[str, WrapperRule] = {}
    for name, raw_rule in wrappers_data.items():
        rule = raw_rule if isinstance(raw_rule, Mapping) else {}
        symbol_args = _int_tuple(rule.get("symbol_args", ()))
        symbol_arg = int(rule.get("symbol_arg", symbol_args[0] if symbol_args else 0))
        wrappers[str(name)] = WrapperRule(
            symbol_arg=symbol_arg,
            access=str(rule.get("access", "reference")),
            symbol_args=symbol_args,
        )
    return wrappers


def _iter_configured_cpp_calls(source: str, profile: ResolverProfile) -> Iterable[tuple[str, str]]:
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", source, flags=re.DOTALL):
        wrapper = match.group(1)
        if wrapper not in profile.wrappers:
            continue
        open_index = match.end() - 1
        close_index = _find_matching_paren(source, open_index)
        if close_index == -1:
            continue
        yield wrapper, source[open_index + 1 : close_index]


def _find_matching_paren(source: str, open_index: int) -> int:
    depth = 0
    quote: Optional[str] = None
    escaped = False
    for index in range(open_index, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _symbols_from_arg(arg: str, profile: ResolverProfile) -> List[str]:
    nested = resolve_cpp_register_calls(arg, profile)
    symbols: List[str] = []
    for item in nested:
        if item.symbol not in symbols:
            symbols.append(item.symbol)
    return symbols


def _symbols_for_argument(arg: str, profile: ResolverProfile) -> List[str]:
    symbols = _symbols_from_arg(arg, profile) or _prefixed_symbols_in_expression(arg, profile) or [
        _fallback_symbol_for_argument(arg, profile)
    ]
    return [symbol for symbol in symbols if symbol]


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


def _prefixed_symbols_in_expression(raw: str, profile: ResolverProfile) -> List[str]:
    prefixes = [prefix for prefix in profile.symbol_prefixes if prefix]
    if not prefixes:
        return []
    pattern = re.compile(
        r"\b("
        + "|".join(re.escape(prefix) for prefix in sorted(prefixes, key=len, reverse=True))
        + r")([A-Z][A-Za-z0-9_]*)\b"
    )
    symbols: List[str] = []
    for match in pattern.finditer(raw):
        symbol = match.group(2)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _fallback_symbol_for_argument(raw: str, profile: ResolverProfile) -> str:
    candidate = raw.strip().strip("&*")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
        return ""
    symbol = _canonical_symbol(candidate, profile.symbol_prefixes)
    if symbol != candidate:
        return symbol
    if symbol.islower():
        return ""
    return symbol


def _int_tuple(value: object) -> tuple[int, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(int(item) for item in value)
    return (int(value),)


def _string_list(value: object) -> List[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return [str(value)]


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
