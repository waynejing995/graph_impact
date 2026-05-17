"""Deterministic source-code graph extraction.

This module is Stage 1 of graph building. It uses clang when available to
identify function spans, then applies configured resolver profiles inside
those spans to produce deterministic function/register edges. Field names,
macro wrappers, and source paths are retained as provenance, not graph nodes.
LLM semantic edges are generated later and must not be conflated with this
stage.
"""

from __future__ import annotations

import re
import json
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

from .graph_filters import is_graph_entity_endpoint
from .resolver_profiles import ResolverProfile, ResolvedSymbol, resolve_cpp_register_calls


@dataclass(frozen=True)
class CodeGraphEdge:
    src: str
    dst: str
    relation: str
    confidence: float
    stage: str = "deterministic"
    source: str = "clang_ast"
    path: str = ""
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    provenance: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DeterministicCodeGraph:
    stage: str
    analysis_mode: str
    path: str
    edges: List[CodeGraphEdge]
    diagnostics: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class _FunctionSpan:
    name: str
    offset_start: int
    offset_end: int
    line_start: int
    line_end: int


def build_deterministic_code_graph(
    source_path: Path,
    source_root: Optional[Path] = None,
    resolver_profiles: Iterable[ResolverProfile] = (),
    clang_args: Iterable[str] = (),
) -> DeterministicCodeGraph:
    source_path = source_path.expanduser()
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    display_path = _display_path(source_path, source_root)
    compile_args = _compile_command_args(source_path, source_root)
    effective_clang_args = [*compile_args, *list(clang_args)]
    spans, analysis_mode, diagnostics = _function_spans_from_clang(source_path, source_text, effective_clang_args)
    if not spans:
        spans = _function_spans_from_text(source_text)
        analysis_mode = "text_fallback"
        diagnostics.append("clang did not return function spans; used text fallback")
    preprocessed_text = _clang_preprocess(source_path, effective_clang_args, diagnostics) if effective_clang_args else ""
    preprocessed_spans = {
        span.name: span
        for span in _function_spans_from_text(preprocessed_text)
    } if preprocessed_text else {}

    profiles = [profile for profile in resolver_profiles if profile.language in {"c", "cpp", "c++"}]
    edges: List[CodeGraphEdge] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for span in spans:
        function_text = source_text[span.offset_start : span.offset_end + 1]
        function_line_start = max(1, span.line_start)
        analysis_inputs = [(function_text, analysis_mode)]
        preprocessed_span = preprocessed_spans.get(span.name)
        if preprocessed_span is not None:
            preprocessed_function_text = preprocessed_text[
                preprocessed_span.offset_start : preprocessed_span.offset_end + 1
            ]
            if preprocessed_function_text and preprocessed_function_text != function_text:
                analysis_inputs.append((preprocessed_function_text, "clang_preprocess"))
        for analysis_text, edge_source in analysis_inputs:
            for profile in profiles:
                for resolved in resolve_cpp_register_calls(analysis_text, profile):
                    if not is_graph_entity_endpoint(resolved.symbol):
                        continue
                    relation = _function_relation_for_resolved(resolved)
                    line_number = _line_for_symbol(source_text, span.offset_start, resolved.symbol, function_line_start)
                    _append_edge(
                        edges,
                        seen,
                        CodeGraphEdge(
                            src=span.name,
                            dst=resolved.symbol,
                            relation=relation,
                            confidence=0.97,
                            source=edge_source,
                            path=display_path,
                            line_start=line_number,
                            line_end=line_number,
                            provenance={
                                "extractor": "code_graph",
                                "function": span.name,
                                "resolver_profile": resolved.profile_id,
                                "wrapper": resolved.wrapper,
                                "symbol_argument": resolved.symbol_argument,
                                "field": resolved.field_symbol,
                                "analysis_mode": edge_source,
                            },
                        ),
                    )
    return DeterministicCodeGraph(
        stage="deterministic",
        analysis_mode=analysis_mode,
        path=display_path,
        edges=edges,
        diagnostics=diagnostics,
    )


def _append_edge(
    edges: List[CodeGraphEdge],
    seen: set[tuple[str, str, str, int, int]],
    edge: CodeGraphEdge,
) -> None:
    key = (edge.src, edge.relation, edge.dst, int(edge.line_start or 0), int(edge.line_end or 0))
    if key in seen:
        return
    seen.add(key)
    edges.append(edge)


def _function_spans_from_clang(
    source_path: Path,
    source_text: str,
    clang_args: Iterable[str],
) -> tuple[List[_FunctionSpan], str, List[str]]:
    command = [
        "clang",
        "-std=gnu89",
        "-Wno-everything",
        "-Xclang",
        "-ast-dump",
        "-fsyntax-only",
        *list(clang_args),
        str(source_path),
    ]
    diagnostics: List[str] = []
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], "clang_unavailable", [str(exc)]
    if completed.stderr.strip():
        diagnostics.append(completed.stderr.strip()[:2000])
    if "FunctionDecl" in completed.stdout:
        return _function_spans_from_text(source_text), "clang_ast", diagnostics
    return [], "clang_ast_failed", diagnostics


def _clang_preprocess(source_path: Path, clang_args: Iterable[str], diagnostics: List[str]) -> str:
    command = ["clang", "-E", "-P", *list(clang_args), str(source_path)]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        diagnostics.append(str(exc))
        return ""
    if completed.stderr.strip():
        diagnostics.append(completed.stderr.strip()[:2000])
    return completed.stdout


def _compile_command_args(source_path: Path, source_root: Optional[Path]) -> List[str]:
    compile_db = _find_compile_commands(source_path, source_root)
    if compile_db is None:
        return []
    try:
        entries = json.loads(compile_db.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(entries, list):
        return []
    source_resolved = source_path.resolve()
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        directory = Path(str(entry.get("directory") or compile_db.parent)).expanduser()
        file_value = str(entry.get("file") or "")
        if not file_value:
            continue
        candidate = Path(file_value)
        if not candidate.is_absolute():
            candidate = directory / candidate
        try:
            if candidate.resolve() != source_resolved:
                continue
        except OSError:
            continue
        raw_args = entry.get("arguments")
        if isinstance(raw_args, list):
            command_args = [str(arg) for arg in raw_args]
        else:
            command = str(entry.get("command") or "")
            command_args = shlex.split(command) if command else []
        return _sanitize_compile_command_args(command_args, directory, source_resolved)
    return []


def _find_compile_commands(source_path: Path, source_root: Optional[Path]) -> Optional[Path]:
    candidates: List[Path] = []
    if source_root:
        candidates.append(source_root.expanduser() / "compile_commands.json")
    candidates.extend(parent / "compile_commands.json" for parent in [source_path.parent, *source_path.parents])
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            return candidate
    return None


def _sanitize_compile_command_args(command_args: List[str], directory: Path, source_path: Path) -> List[str]:
    if not command_args:
        return []
    args = command_args[1:]
    sanitized: List[str] = []
    skip_next = False
    path_flags = {"-I", "-isystem", "-iquote", "-include", "-imacros", "-idirafter"}
    skip_value_flags = {"-o", "-MF", "-MT", "-MQ", "-MJ"}
    skip_flags = {"-c", "-MD", "-MMD", "-MP"}
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in skip_flags:
            continue
        if arg in skip_value_flags:
            skip_next = True
            continue
        if arg in path_flags:
            if index + 1 < len(args):
                sanitized.extend([arg, _absolute_compile_path(args[index + 1], directory)])
                skip_next = True
            continue
        if any(arg.startswith(prefix) and len(arg) > len(prefix) for prefix in ("-I",)):
            sanitized.append(f"-I{_absolute_compile_path(arg[2:], directory)}")
            continue
        if Path(arg).expanduser() == source_path or Path(arg).name == source_path.name:
            continue
        sanitized.append(arg)
    return sanitized


def _absolute_compile_path(value: str, directory: Path) -> str:
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((directory / path).resolve())


def _function_spans_from_text(source_text: str) -> List[_FunctionSpan]:
    pattern = re.compile(
        r"(?m)^\s*(?:static[ \t]+)?(?:inline[ \t]+)?(?:[A-Za-z_][\w \t\*]*[ \t]+)+(?P<name>[A-Za-z_]\w*)[ \t]*\([^\n;{}]*\)[ \t]*(?:\n[ \t]*)?\{"
    )
    spans: List[_FunctionSpan] = []
    for match in pattern.finditer(source_text):
        close = _matching_brace(source_text, match.end() - 1)
        if close == -1:
            continue
        spans.append(
            _FunctionSpan(
                name=match.group("name"),
                offset_start=match.start(),
                offset_end=close,
                line_start=_line_number_for_offset(source_text, match.start()),
                line_end=_line_number_for_offset(source_text, close),
            )
        )
    return spans


def _matching_brace(source_text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(source_text)):
        if source_text[index] == "{":
            depth += 1
        elif source_text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _function_relation_for_resolved(resolved: ResolvedSymbol) -> str:
    if resolved.access == "read":
        return "reads"
    if resolved.access == "write":
        return "writes"
    if resolved.access == "field_set":
        return "sets_field"
    if resolved.access in {"field_write", "field_value"}:
        return "writes"
    if resolved.access in {"field_get", "field_read", "field_mask", "field_shift"}:
        return "reads"
    if resolved.access == "address":
        return "maps_base"
    return resolved.access or "mentions"


def _line_for_symbol(source_text: str, span_start: int, symbol: str, default_line: int) -> int:
    index = source_text.find(symbol, span_start)
    if index == -1:
        return default_line
    return _line_number_for_offset(source_text, index)


def _line_number_for_offset(source_text: str, offset: int) -> int:
    return source_text.count("\n", 0, max(0, offset)) + 1


def _display_path(source_path: Path, source_root: Optional[Path]) -> str:
    if source_root:
        try:
            return source_path.resolve().relative_to(source_root.expanduser().resolve()).as_posix()
        except ValueError:
            pass
    return source_path.name
