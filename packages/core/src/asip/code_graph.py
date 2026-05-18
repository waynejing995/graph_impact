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
from typing import Any, Iterable, List, Mapping, Optional

from .graph_filters import is_graph_entity_endpoint
from .resolver_profiles import ResolverProfile, ResolvedSymbol, resolve_cpp_register_calls


@dataclass(frozen=True)
class CodeGraphEdge:
    src: str
    dst: str
    relation: str
    confidence: float
    stage: str = "deterministic"
    source: str = "clang_text_spans"
    path: str = ""
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    provenance: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeGraphCallbackSlot:
    slot: str
    function: str
    table: str
    table_type: str = ""
    initializer_flow: str = "text"
    path: str = ""
    function_path: str = ""
    line_start: Optional[int] = None
    assignment_line_start: Optional[int] = None
    function_line_start: Optional[int] = None


@dataclass(frozen=True)
class CodeGraphSlotCall:
    caller: str
    slot: str
    receiver: str = ""
    receiver_type: str = ""
    receiver_tables: tuple[str, ...] = ()
    type_flow: str = ""
    path: str = ""
    line_start: Optional[int] = None


@dataclass(frozen=True)
class CodeGraphFunctionLocation:
    name: str
    path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass(frozen=True)
class CodeGraphVersionFieldSink:
    function: str
    target_arg_index: int
    value_arg_index: int
    target_suffix: str


@dataclass(frozen=True)
class DeterministicCodeGraph:
    stage: str
    analysis_mode: str
    path: str
    edges: List[CodeGraphEdge]
    diagnostics: List[str] = field(default_factory=list)
    callback_slots: List[CodeGraphCallbackSlot] = field(default_factory=list)
    slot_calls: List[CodeGraphSlotCall] = field(default_factory=list)


@dataclass(frozen=True)
class _FunctionSpan:
    name: str
    offset_start: int
    offset_end: int
    line_start: int
    line_end: int


@dataclass(frozen=True)
class _AstSlotCallHint:
    receiver_type: str
    type_flow: str


_CONTROL_KEYWORD_NAMES = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
}

_GENERIC_CALLBACK_RECEIVERS = {"funcs", "ops", "callbacks", "init_func", "init_funcs"}
_CALLBACK_TYPE_BY_RECEIVER = {
    "funcs": "amd_ip_funcs",
    "init_func": "amdgv_init_func",
    "init_funcs": "amdgv_init_func",
}
_CALLBACK_TYPE_BY_RECEIVER_SUFFIX = (
    ("gfx.rlc.funcs", "amdgpu_rlc_funcs"),
    ("rlc.funcs", "amdgpu_rlc_funcs"),
    ("gfx.imu.funcs", "amdgpu_imu_funcs"),
    ("imu.funcs", "amdgpu_imu_funcs"),
    ("gfxhub.funcs", "amdgpu_gfxhub_funcs"),
    ("mmhub.funcs", "amdgpu_mmhub_funcs"),
    ("nbio.funcs", "amdgpu_nbio_funcs"),
    ("df.funcs", "amdgpu_df_funcs"),
    ("smuio.funcs", "amdgpu_smuio_funcs"),
    ("umc.funcs", "amdgpu_umc_funcs"),
    ("hdp.funcs", "amdgpu_hdp_funcs"),
    ("sdma.funcs", "amdgpu_sdma_funcs"),
    ("gfx.funcs", "amdgpu_gfx_funcs"),
    ("version->funcs", "amd_ip_funcs"),
    ("version.funcs", "amd_ip_funcs"),
)


def build_deterministic_code_graph(
    source_path: Path,
    source_root: Optional[Path] = None,
    resolver_profiles: Iterable[ResolverProfile] = (),
    clang_args: Iterable[str] = (),
    known_function_locations: Optional[Mapping[str, Iterable[CodeGraphFunctionLocation]]] = None,
    known_table_field_aliases: Optional[Mapping[str, Iterable[str]]] = None,
    known_version_field_sinks: Optional[Mapping[str, Iterable[CodeGraphVersionFieldSink]]] = None,
    known_receiver_table_aliases: Optional[Mapping[str, Iterable[str]]] = None,
    known_return_table_aliases: Optional[Mapping[str, Iterable[str]]] = None,
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
    ast_json = _clang_ast_json(
        source_path,
        source_text,
        effective_clang_args,
        diagnostics,
    )
    ast_slot_call_hints = _clang_ast_json_slot_call_hints(source_text, ast_json, diagnostics)
    preprocessed_text = _clang_preprocess(source_path, effective_clang_args, diagnostics) if effective_clang_args else ""
    preprocessed_spans = {
        span.name: span
        for span in _function_spans_from_text(preprocessed_text)
    } if preprocessed_text else {}

    profiles = [profile for profile in resolver_profiles if profile.language in {"c", "cpp", "c++"}]
    edges: List[CodeGraphEdge] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    function_names = {span.name for span in spans}
    known_locations = known_function_locations or {}
    known_function_names = set(known_locations)
    callable_function_names = function_names | known_function_names
    function_lines = {span.name: span.line_start for span in spans}
    callback_slots = _merge_callback_slots(
        _callback_slots_from_text(
            source_text,
            function_names,
            function_lines,
            display_path,
            known_locations,
        ),
        _clang_ast_json_callback_slots(
            source_text,
            ast_json,
            display_path,
            function_names,
            function_lines,
            known_locations,
            diagnostics,
        ),
    )
    table_field_aliases = _merge_table_field_aliases(
        known_table_field_aliases or {},
        _table_field_aliases_from_text(source_text),
    )
    version_field_sinks = _merge_version_field_sinks(
        known_version_field_sinks or {},
        _version_field_sinks_from_spans(source_text, spans),
    )
    return_table_aliases = _merge_table_field_aliases(
        known_return_table_aliases or {},
        _return_table_aliases_from_spans(source_text, spans),
    )
    receiver_table_aliases = _merge_table_field_aliases(
        known_receiver_table_aliases or {},
        _direct_receiver_table_aliases_from_text(source_text),
        _receiver_table_aliases_from_version_sink_calls(source_text, spans, version_field_sinks),
    )
    slot_calls: List[CodeGraphSlotCall] = []
    for span in spans:
        function_text = source_text[span.offset_start : span.offset_end + 1]
        function_line_start = max(1, span.line_start)
        for callee, call_offset in _direct_function_calls(function_text, callable_function_names, span.name):
            line_number = _line_number_for_offset(source_text, span.offset_start + call_offset)
            callee_location = _callee_location_for_direct_call(
                callee,
                display_path,
                function_lines,
                known_locations,
            )
            if callee_location is None:
                continue
            _append_edge(
                edges,
                seen,
                CodeGraphEdge(
                    src=span.name,
                    dst=callee,
                    relation="calls",
                    confidence=0.9,
                    source=analysis_mode,
                    path=display_path,
                    line_start=line_number,
                    line_end=line_number,
                    provenance={
                        "extractor": "code_graph",
                        "function": span.name,
                        "callee": callee,
                        "call_kind": "direct",
                        "callee_path": callee_location.path,
                        "callee_line": callee_location.line_start,
                        "analysis_mode": analysis_mode,
                    },
                ),
            )
        for receiver, slot, slot_offset, receiver_type, receiver_tables, alias_type_flow in _slot_calls_for_function(
            function_text,
            table_field_aliases,
            version_field_sinks,
            receiver_table_aliases,
            return_table_aliases,
        ):
            line_number = _line_number_for_offset(source_text, span.offset_start + slot_offset)
            ast_hint = _ast_slot_call_hint_for(
                ast_slot_call_hints,
                span.name,
                receiver,
                slot,
                line_number,
            )
            slot_calls.append(
                CodeGraphSlotCall(
                    caller=span.name,
                    slot=slot,
                    receiver=receiver,
                    receiver_type=ast_hint.receiver_type if ast_hint and ast_hint.receiver_type else receiver_type,
                    receiver_tables=receiver_tables,
                    type_flow=ast_hint.type_flow if ast_hint else alias_type_flow,
                    path=display_path,
                    line_start=line_number,
                )
            )
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
    callbacks_by_slot: dict[str, list[CodeGraphCallbackSlot]] = {}
    for callback in callback_slots:
        callbacks_by_slot.setdefault(callback.slot, []).append(callback)
    for slot_call in slot_calls:
        callbacks = _callbacks_for_slot_call(slot_call, callbacks_by_slot)
        call_kind = _callback_call_kind(slot_call, callbacks)
        confidence = 0.72 if call_kind == "vtable_dispatch" else 0.84
        for callback in callbacks:
            if callback.function == slot_call.caller:
                continue
            _append_edge(
                edges,
                seen,
                CodeGraphEdge(
                    src=slot_call.caller,
                    dst=callback.function,
                    relation="calls",
                    confidence=confidence,
                    source="clang_callback",
                    path=slot_call.path,
                    line_start=slot_call.line_start,
                    line_end=slot_call.line_start,
                    provenance={
                        "extractor": "code_graph",
                        "function": slot_call.caller,
                        "callee": callback.function,
                        "call_kind": call_kind,
                        "slot": slot_call.slot,
                        "receiver": slot_call.receiver,
                        "receiver_type": slot_call.receiver_type,
                        "receiver_tables": list(slot_call.receiver_tables),
                        "type_flow": slot_call.type_flow,
                        "callback_table": callback.table,
                        "callback_table_type": callback.table_type,
                        "callback_initializer_flow": callback.initializer_flow,
                        "callback_candidate_count": len(callbacks),
                        "dispatch_scope": "generic_slot" if call_kind == "vtable_dispatch" else "matched_slot",
                        "callee_path": callback.function_path or callback.path,
                        "callback_path": callback.path,
                        "callee_line": callback.function_line_start,
                        "callback_line": callback.assignment_line_start or callback.line_start,
                        "analysis_mode": analysis_mode,
                    },
                ),
            )
    return DeterministicCodeGraph(
        stage="deterministic",
        analysis_mode=analysis_mode,
        path=display_path,
        edges=edges,
        diagnostics=diagnostics,
        callback_slots=callback_slots,
        slot_calls=slot_calls,
    )


def collect_code_graph_function_locations(
    source_path: Path,
    source_root: Optional[Path] = None,
    clang_args: Iterable[str] = (),
) -> List[CodeGraphFunctionLocation]:
    source_path = source_path.expanduser()
    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    spans = _function_spans_from_text(source_text)
    display_path = _display_path(source_path, source_root)
    return [
        CodeGraphFunctionLocation(
            name=span.name,
            path=display_path,
            line_start=span.line_start,
            line_end=span.line_end,
        )
        for span in spans
    ]


def collect_code_graph_table_field_aliases(source_path: Path) -> Mapping[str, tuple[str, ...]]:
    source_path = source_path.expanduser()
    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return _table_field_aliases_from_text(source_text)


def collect_code_graph_version_field_sinks(source_path: Path) -> Mapping[str, tuple[CodeGraphVersionFieldSink, ...]]:
    source_path = source_path.expanduser()
    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    spans = _function_spans_from_text(source_text)
    return _version_field_sinks_from_spans(source_text, spans)


def collect_code_graph_receiver_table_aliases(
    source_path: Path,
    known_version_field_sinks: Mapping[str, Iterable[CodeGraphVersionFieldSink]],
) -> Mapping[str, tuple[str, ...]]:
    source_path = source_path.expanduser()
    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    spans = _function_spans_from_text(source_text)
    return _merge_table_field_aliases(
        _direct_receiver_table_aliases_from_text(source_text),
        _receiver_table_aliases_from_version_sink_calls(source_text, spans, known_version_field_sinks),
    )


def collect_code_graph_return_table_aliases(source_path: Path) -> Mapping[str, tuple[str, ...]]:
    source_path = source_path.expanduser()
    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    spans = _function_spans_from_text(source_text)
    return _return_table_aliases_from_spans(source_text, spans)


def _merge_table_field_aliases(
    *alias_maps: Mapping[str, Iterable[str]],
) -> dict[str, tuple[str, ...]]:
    merged: dict[str, list[str]] = {}
    for alias_map in alias_maps:
        for key, values in alias_map.items():
            merged.setdefault(str(key), [])
            for value in values:
                value_text = str(value)
                if value_text and value_text not in merged[str(key)]:
                    merged[str(key)].append(value_text)
    return {key: tuple(values) for key, values in merged.items()}


def _merge_version_field_sinks(
    *sink_maps: Mapping[str, Iterable[CodeGraphVersionFieldSink]],
) -> dict[str, tuple[CodeGraphVersionFieldSink, ...]]:
    merged: dict[str, list[CodeGraphVersionFieldSink]] = {}
    seen: set[CodeGraphVersionFieldSink] = set()
    for sink_map in sink_maps:
        for key, values in sink_map.items():
            merged.setdefault(str(key), [])
            for value in values:
                if value in seen:
                    continue
                seen.add(value)
                merged[str(key)].append(value)
    return {key: tuple(values) for key, values in merged.items()}


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
        diagnostics.append("clang ast-dump succeeded; function spans are derived from source text")
        return _function_spans_from_text(source_text), "clang_text_spans", diagnostics
    return [], "clang_ast_failed", diagnostics


def _clang_ast_json(
    source_path: Path,
    source_text: str,
    clang_args: Iterable[str],
    diagnostics: List[str],
) -> Optional[Mapping[str, Any]]:
    if not _source_may_have_ast_json_callback_data(source_text):
        return None
    command = [
        "clang",
        "-std=gnu89",
        "-Wno-everything",
        "-Xclang",
        "-ast-dump=json",
        "-fsyntax-only",
        *list(clang_args),
        str(source_path),
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        diagnostics.append(str(exc))
        return None
    if not completed.stdout.strip().startswith("{"):
        if completed.stderr.strip():
            diagnostics.append(completed.stderr.strip()[:2000])
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def _clang_ast_json_slot_call_hints(
    source_text: str,
    ast: Optional[Mapping[str, Any]],
    diagnostics: List[str],
) -> dict[tuple[str, str, str, int], _AstSlotCallHint]:
    if ast is None or not _source_may_have_slot_calls(source_text):
        return {}
    hints: dict[tuple[str, str, str, int], _AstSlotCallHint] = {}
    for function in _ast_nodes(ast, "FunctionDecl"):
        function_name = str(function.get("name") or "").strip()
        if not function_name:
            continue
        for call in _ast_nodes(function, "CallExpr"):
            callee_expression = _first_ast_child(call)
            member = _first_ast_node(callee_expression, "MemberExpr")
            if not member:
                continue
            slot = str(member.get("name") or "").strip()
            if not slot:
                continue
            receiver = _receiver_text_for_ast_member(source_text, member, slot)
            receiver_type = _receiver_type_for_ast_member(member)
            line_number = _ast_line_number(source_text, member)
            if not receiver or not receiver_type or not line_number:
                continue
            hints[(
                function_name,
                _normalize_receiver_path(receiver),
                slot,
                line_number,
            )] = _AstSlotCallHint(receiver_type=receiver_type, type_flow="clang_ast_json")
    if hints:
        diagnostics.append(f"clang ast json provided {len(hints)} typed callback receiver hints")
    return hints


def _clang_ast_json_callback_slots(
    source_text: str,
    ast: Optional[Mapping[str, Any]],
    display_path: str,
    function_names: set[str],
    function_lines: Mapping[str, int],
    known_function_locations: Mapping[str, Iterable[CodeGraphFunctionLocation]],
    diagnostics: List[str],
) -> List[CodeGraphCallbackSlot]:
    if ast is None or not _source_may_have_callback_initializers(source_text):
        return []
    callbacks: List[CodeGraphCallbackSlot] = []
    for variable in _ast_nodes(ast, "VarDecl"):
        table = str(variable.get("name") or "").strip()
        if not table:
            continue
        table_type = _normalize_callback_table_type(_ast_qual_type(variable))
        if not table_type and not _looks_like_callback_table_name(table):
            continue
        for reference in _ast_nodes(variable, "DeclRefExpr"):
            callback = _ast_referenced_function_name(reference)
            if not callback:
                callback = _source_identifier_for_ast_reference(source_text, reference)
            if not callback:
                continue
            callback_location = _callback_function_location(
                callback,
                display_path,
                function_names,
                function_lines,
                known_function_locations,
            )
            if callback_location is None:
                continue
            slot = _slot_name_for_ast_callback_reference(source_text, reference)
            if not slot:
                continue
            assignment_line = _assignment_line_for_ast_callback_reference(source_text, reference)
            callbacks.append(
                CodeGraphCallbackSlot(
                    slot=slot,
                    function=callback,
                    table=table,
                    table_type=table_type,
                    initializer_flow="clang_ast_json",
                    path=display_path,
                    function_path=callback_location.path,
                    line_start=assignment_line,
                    assignment_line_start=assignment_line,
                    function_line_start=callback_location.line_start,
                )
            )
    if callbacks:
        diagnostics.append(f"clang ast json provided {len(callbacks)} typed callback initializers")
    return callbacks


def _merge_callback_slots(*slot_groups: Iterable[CodeGraphCallbackSlot]) -> List[CodeGraphCallbackSlot]:
    merged: List[CodeGraphCallbackSlot] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    for group in slot_groups:
        for slot in group:
            key = (
                slot.slot,
                slot.function,
                slot.table,
                slot.path,
                int(slot.assignment_line_start or slot.line_start or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(slot)
    return merged


def _source_may_have_ast_json_callback_data(source_text: str) -> bool:
    return _source_may_have_slot_calls(source_text) or _source_may_have_callback_initializers(source_text)


def _source_may_have_slot_calls(source_text: str) -> bool:
    return bool(re.search(r"(?:->|\.)\s*[A-Za-z_]\w*\s*\)?\s*\(", source_text))


def _source_may_have_callback_initializers(source_text: str) -> bool:
    if not re.search(r"\b(?:funcs|ops|callbacks|func)\b", source_text):
        return False
    if re.search(r"\.[A-Za-z_]\w*\s*=", source_text):
        return True
    return bool(re.search(r"\b[A-Za-z_]\w*\s*\(\s*[A-Za-z_]\w*\s*,\s*[A-Za-z_]\w*", source_text))


def _ast_nodes(node: Any, kind: str) -> Iterable[Mapping[str, Any]]:
    if not isinstance(node, Mapping):
        return
    if node.get("kind") == kind:
        yield node
    inner = node.get("inner")
    if not isinstance(inner, list):
        return
    for child in inner:
        yield from _ast_nodes(child, kind)


def _first_ast_child(node: Any) -> Optional[Mapping[str, Any]]:
    if not isinstance(node, Mapping):
        return None
    inner = node.get("inner")
    if not isinstance(inner, list) or not inner:
        return None
    first = inner[0]
    return first if isinstance(first, Mapping) else None


def _first_ast_node(node: Any, kind: str) -> Optional[Mapping[str, Any]]:
    if not isinstance(node, Mapping):
        return None
    if node.get("kind") == kind:
        return node
    inner = node.get("inner")
    if not isinstance(inner, list):
        return None
    for child in inner:
        found = _first_ast_node(child, kind)
        if found is not None:
            return found
    return None


def _receiver_text_for_ast_member(source_text: str, member: Mapping[str, Any], slot: str) -> str:
    node_range = member.get("range")
    if not isinstance(node_range, Mapping):
        return ""
    begin = node_range.get("begin")
    end = node_range.get("end")
    if not isinstance(begin, Mapping) or not isinstance(end, Mapping):
        return ""
    start = _ast_location_offset(begin)
    end_offset = _ast_location_offset(end)
    token_length = int(end.get("tokLen") or 0)
    if start < 0 or end_offset < start:
        return ""
    expression = source_text[start : end_offset + max(1, token_length)]
    expression = re.sub(r"\s+", "", expression)
    expression = re.sub(rf"(?:->|\.){re.escape(slot)}\s*$", "", expression)
    return expression.strip("()")


def _receiver_type_for_ast_member(member: Mapping[str, Any]) -> str:
    receiver = _first_ast_child(member)
    if receiver is None:
        return ""
    qual_type = _ast_qual_type(receiver)
    return _normalize_callback_table_type(qual_type)


def _ast_qual_type(node: Mapping[str, Any]) -> str:
    node_type = node.get("type")
    if isinstance(node_type, Mapping):
        qual_type = str(node_type.get("qualType") or "").strip()
        if qual_type:
            return qual_type
    child = _first_ast_child(node)
    return _ast_qual_type(child) if child is not None else ""


def _ast_referenced_function_name(node: Mapping[str, Any]) -> str:
    referenced = node.get("referencedDecl")
    if not isinstance(referenced, Mapping) or referenced.get("kind") != "FunctionDecl":
        return ""
    name = str(referenced.get("name") or "").strip()
    return "" if _looks_like_preprocessor_macro(name) else name


def _source_identifier_for_ast_reference(source_text: str, node: Mapping[str, Any]) -> str:
    offset = _ast_node_spelling_offset(node)
    if offset < 0:
        return ""
    match = re.match(r"[A-Za-z_]\w*", source_text[offset:])
    if not match:
        return ""
    name = match.group(0)
    return "" if _looks_like_preprocessor_macro(name) else name


def _slot_name_for_ast_callback_reference(source_text: str, node: Mapping[str, Any]) -> str:
    slot_match = _slot_match_for_ast_callback_reference(source_text, node)
    return slot_match[0] if slot_match else ""


def _assignment_line_for_ast_callback_reference(source_text: str, node: Mapping[str, Any]) -> int:
    slot_match = _slot_match_for_ast_callback_reference(source_text, node)
    if slot_match:
        return _line_number_for_offset(source_text, slot_match[1])
    offset = _ast_node_spelling_offset(node)
    return _line_number_for_offset(source_text, offset) if offset >= 0 else 0


def _slot_match_for_ast_callback_reference(source_text: str, node: Mapping[str, Any]) -> Optional[tuple[str, int]]:
    offset = _ast_node_spelling_offset(node)
    if offset < 0:
        return None
    start = max(source_text.rfind("{", 0, offset), source_text.rfind(",", 0, offset), source_text.rfind("\n", 0, offset))
    prefix_start = start + 1
    prefix = source_text[prefix_start:offset]
    matches = list(re.finditer(r"\.(?P<slot>[A-Za-z_]\w*)\s*=", prefix))
    if matches:
        match = matches[-1]
        return match.group("slot"), prefix_start + match.start("slot") - 1
    line_start = source_text.rfind("\n", 0, offset) + 1
    line_prefix = source_text[line_start:offset]
    macro_matches = list(
        re.finditer(r"\b[A-Za-z_]\w*\s*\(\s*(?P<slot>[A-Za-z_]\w*)\s*,[^()\n]*$", line_prefix)
    )
    if not macro_matches:
        return None
    match = macro_matches[-1]
    return match.group("slot"), line_start + match.start("slot")


def _ast_node_spelling_offset(node: Mapping[str, Any]) -> int:
    node_range = node.get("range")
    if not isinstance(node_range, Mapping):
        return -1
    begin = node_range.get("begin")
    if not isinstance(begin, Mapping):
        return -1
    return _ast_location_offset(begin, prefer_spelling=True)


def _ast_location_offset(location: Mapping[str, Any], prefer_spelling: bool = False) -> int:
    offset = location.get("offset")
    if isinstance(offset, int):
        return offset
    nested_keys = ("spellingLoc", "expansionLoc") if prefer_spelling else ("expansionLoc", "spellingLoc")
    for key in nested_keys:
        nested = location.get(key)
        if isinstance(nested, Mapping):
            nested_offset = nested.get("offset")
            if isinstance(nested_offset, int):
                return nested_offset
    return -1


def _normalize_callback_table_type(qual_type: str) -> str:
    cleaned = qual_type.strip()
    cleaned = re.sub(r"\b(?:const|volatile|restrict)\b", "", cleaned)
    cleaned = cleaned.replace("*", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    match = re.search(r"\bstruct\s+([A-Za-z_]\w*(?:_funcs|_ops|_callbacks|_func))\b", cleaned)
    if match:
        return match.group(1)
    match = re.search(r"\b([A-Za-z_]\w*(?:_funcs|_ops|_callbacks|_func))\b", cleaned)
    return match.group(1) if match else ""


def _ast_line_number(source_text: str, node: Mapping[str, Any]) -> int:
    node_range = node.get("range")
    if not isinstance(node_range, Mapping):
        return 0
    begin = node_range.get("begin")
    if not isinstance(begin, Mapping):
        return 0
    offset = _ast_location_offset(begin)
    return _line_number_for_offset(source_text, offset) if offset >= 0 else 0


def _ast_slot_call_hint_for(
    hints: Mapping[tuple[str, str, str, int], _AstSlotCallHint],
    function_name: str,
    receiver: str,
    slot: str,
    line_number: int,
) -> Optional[_AstSlotCallHint]:
    return hints.get((function_name, _normalize_receiver_path(receiver), slot, line_number))


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
        r"(?m)^\s*(?:static[ \t]+)?(?:inline[ \t]+)?(?:[A-Za-z_][\w \t\*]*[ \t]+)+(?P<name>[A-Za-z_]\w*)[ \t]*\([^;{}]*\)[ \t]*(?:\n[ \t]*)?\{"
    )
    spans: List[_FunctionSpan] = []
    for match in pattern.finditer(source_text):
        function_name = match.group("name")
        if function_name in _CONTROL_KEYWORD_NAMES or _looks_like_preprocessor_macro(function_name):
            continue
        close = _matching_brace(source_text, match.end() - 1)
        if close == -1:
            continue
        spans.append(
            _FunctionSpan(
                name=function_name,
                offset_start=match.start(),
                offset_end=close,
                line_start=_line_number_for_offset(source_text, match.start()),
                line_end=_line_number_for_offset(source_text, close),
            )
        )
    return spans


def _callback_slots_from_text(
    source_text: str,
    function_names: set[str],
    function_lines: Mapping[str, int],
    display_path: str,
    known_function_locations: Optional[Mapping[str, Iterable[CodeGraphFunctionLocation]]] = None,
) -> List[CodeGraphCallbackSlot]:
    assignment = re.compile(
        r"\.(?P<slot>[A-Za-z_]\w*)\s*=\s*&?\s*(?P<callback>[A-Za-z_]\w*)\b"
    )
    table_name = ""
    table_type = ""
    table_depth = 0
    callbacks: List[CodeGraphCallbackSlot] = []
    known_locations = known_function_locations or {}
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        table_match = re.search(
            r"\b(?:static\s+)?(?:const\s+)?(?:struct\s+)?(?P<table_type>[A-Za-z_]\w*)\s+"
            r"(?P<table>[A-Za-z_]\w*)\s*=\s*\{",
            line,
        )
        if table_match:
            table_name = table_match.group("table")
            table_type = table_match.group("table_type")
            table_depth = line.count("{") - line.count("}")
        elif table_depth <= 0:
            table_name = ""
            table_type = ""
        for match in assignment.finditer(line):
            callback = match.group("callback")
            callback_location = _callback_function_location(
                callback,
                display_path,
                function_names,
                function_lines,
                known_locations,
            )
            if callback_location is None:
                continue
            callbacks.append(
                CodeGraphCallbackSlot(
                    slot=match.group("slot"),
                    function=callback,
                    table=table_name,
                    table_type=table_type,
                    path=display_path,
                    function_path=callback_location.path,
                    line_start=line_number,
                    assignment_line_start=line_number,
                    function_line_start=callback_location.line_start,
                )
            )
        if table_depth > 0 and not table_match:
            table_depth += line.count("{") - line.count("}")
            if table_depth <= 0:
                table_name = ""
                table_type = ""
    return callbacks


def _callback_function_location(
    callback: str,
    display_path: str,
    function_names: set[str],
    function_lines: Mapping[str, int],
    known_function_locations: Mapping[str, Iterable[CodeGraphFunctionLocation]],
) -> Optional[CodeGraphFunctionLocation]:
    if callback in function_names:
        return CodeGraphFunctionLocation(
            name=callback,
            path=display_path,
            line_start=function_lines.get(callback),
        )
    locations = list(known_function_locations.get(callback, ()))
    if len(locations) == 1:
        return locations[0]
    return None


def _direct_function_calls(
    function_text: str,
    function_names: set[str],
    caller: str,
) -> List[tuple[str, int]]:
    calls: List[tuple[str, int]] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b(?P<callee>[A-Za-z_]\w*)\s*\(", function_text):
        callee = match.group("callee")
        if callee == caller or callee not in function_names or _looks_like_preprocessor_macro(callee):
            continue
        if callee not in seen:
            seen.add(callee)
            calls.append((callee, match.start("callee")))
    return calls


def _looks_like_preprocessor_macro(name: str) -> bool:
    """Reject all-caps macro invocations that can mimic C function spans."""

    return bool(name) and name.upper() == name and any(character.isalpha() for character in name)


def _callee_location_for_direct_call(
    callee: str,
    display_path: str,
    local_function_lines: Mapping[str, int],
    known_function_locations: Mapping[str, Iterable[CodeGraphFunctionLocation]],
) -> Optional[CodeGraphFunctionLocation]:
    if callee in local_function_lines:
        return CodeGraphFunctionLocation(callee, display_path, local_function_lines.get(callee))
    locations = list(known_function_locations.get(callee, []))
    if len(locations) == 1:
        return locations[0]
    return None


def _slot_calls_for_function(
    function_text: str,
    table_field_aliases: Optional[Mapping[str, tuple[str, ...]]] = None,
    version_field_sinks: Optional[Mapping[str, Iterable[CodeGraphVersionFieldSink]]] = None,
    global_receiver_table_aliases: Optional[Mapping[str, Iterable[str]]] = None,
    return_table_aliases: Optional[Mapping[str, Iterable[str]]] = None,
) -> List[tuple[str, str, int, str, tuple[str, ...], str]]:
    slots: List[tuple[str, str, int, str, tuple[str, ...], str]] = []
    seen: set[tuple[str, str]] = set()
    active_table_field_aliases = table_field_aliases or {}
    receiver_type_hints = _receiver_type_hints_for_function(function_text)
    local_receiver_aliases, alias_type_flows = _receiver_table_aliases_for_function(
        function_text,
        version_field_sinks or {},
        return_table_aliases or {},
        global_receiver_table_aliases or {},
    )
    receiver_table_aliases = _merge_table_field_aliases(
        global_receiver_table_aliases or {},
        local_receiver_aliases,
    )
    receiver_part = r"[A-Za-z_]\w*(?:\s*\[[^\]]+\])?"
    for match in re.finditer(
        rf"\b(?P<receiver>{receiver_part}(?:\s*(?:->|\.)\s*{receiver_part})*)\s*(?:->|\.)\s*(?P<slot>[A-Za-z_]\w*)\s*\)?\s*\(",
        function_text,
    ):
        receiver = re.sub(r"\s+", "", match.group("receiver"))
        slot = match.group("slot")
        item = (receiver, slot)
        if item not in seen:
            seen.add(item)
            receiver_leaf = _receiver_leaf(receiver)
            receiver_tables = receiver_table_aliases.get(receiver)
            if receiver_tables is None:
                receiver_tables = receiver_table_aliases.get(receiver_leaf, ())
            alias_type_flow = alias_type_flows.get(receiver, "") or alias_type_flows.get(receiver_leaf, "")
            if not receiver_tables:
                receiver_tables = _receiver_tables_from_table_field_alias(
                    receiver,
                    receiver_table_aliases,
                    active_table_field_aliases,
                )
            if not alias_type_flow:
                alias_type_flow = _type_flow_for_receiver_alias(receiver, alias_type_flows)
            slots.append((
                receiver,
                slot,
                match.start("slot"),
                receiver_type_hints.get(receiver_leaf, ""),
                tuple(receiver_tables),
                alias_type_flow,
            ))
    return slots


def _table_field_aliases_from_text(source_text: str) -> dict[str, tuple[str, ...]]:
    field_aliases: dict[str, list[str]] = {}
    table_name = ""
    table_depth = 0
    table_matcher = re.compile(
        r"\b(?:static\s+)?(?:const\s+)?(?:struct\s+)?(?P<table_type>[A-Za-z_]\w*)\s+"
        r"(?P<table>[A-Za-z_]\w*)\s*=\s*\{"
    )
    assignment = re.compile(
        r"\.(?P<field>[A-Za-z_]\w*)\s*=\s*&?\s*(?P<table>[A-Za-z_]\w*)\b"
    )
    for line in source_text.splitlines():
        match = table_matcher.search(line)
        if match:
            table_name = match.group("table")
            table_depth = line.count("{") - line.count("}")
        elif table_depth <= 0:
            table_name = ""
        if table_name:
            for assignment_match in assignment.finditer(line):
                target = assignment_match.group("table")
                if not _looks_like_callback_table_name(target):
                    continue
                key = f"{table_name}.{assignment_match.group('field')}"
                field_aliases.setdefault(key, [])
                if target not in field_aliases[key]:
                    field_aliases[key].append(target)
        if table_depth > 0 and not match:
            table_depth += line.count("{") - line.count("}")
            if table_depth <= 0:
                table_name = ""
    return {key: tuple(values) for key, values in field_aliases.items()}


def _version_field_sinks_from_spans(
    source_text: str,
    spans: Iterable[_FunctionSpan],
) -> dict[str, tuple[CodeGraphVersionFieldSink, ...]]:
    result: dict[str, list[CodeGraphVersionFieldSink]] = {}
    assignment = re.compile(
        r"\b(?P<target>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)"
        r"\s*(?:->|\.)\s*version\s*=\s*(?P<value>[A-Za-z_]\w*)\b"
    )
    for span in spans:
        function_text = source_text[span.offset_start : span.offset_end + 1]
        params = _function_parameter_names(function_text)
        if not params:
            continue
        param_index = {name: index for index, name in enumerate(params)}
        body_open = function_text.find("{")
        body = function_text[body_open + 1 :] if body_open != -1 else function_text
        for match in assignment.finditer(body):
            target = re.sub(r"\s+", "", match.group("target"))
            value = match.group("value")
            target_root_match = re.match(r"[A-Za-z_]\w*", target)
            if not target_root_match:
                continue
            target_root = target_root_match.group(0)
            if target_root not in param_index or value not in param_index:
                continue
            normalized_target = _normalize_receiver_path(target)
            normalized_root = _normalize_receiver_path(target_root)
            target_suffix = normalized_target[len(normalized_root) :].lstrip(".")
            target_suffix = f"{target_suffix}.version" if target_suffix else "version"
            sink = CodeGraphVersionFieldSink(
                function=span.name,
                target_arg_index=param_index[target_root],
                value_arg_index=param_index[value],
                target_suffix=target_suffix,
            )
            result.setdefault(span.name, [])
            if sink not in result[span.name]:
                result[span.name].append(sink)
    return {key: tuple(values) for key, values in result.items()}


def _function_parameter_names(function_text: str) -> list[str]:
    open_index = function_text.find("(")
    close_index = _matching_paren(function_text, open_index)
    if open_index == -1 or close_index == -1:
        return []
    params = _split_call_arguments(function_text[open_index + 1 : close_index])
    names: list[str] = []
    for param in params:
        identifiers = re.findall(r"\b[A-Za-z_]\w*\b", param)
        if not identifiers or identifiers == ["void"]:
            continue
        names.append(identifiers[-1])
    return names


def _split_call_arguments(argument_text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(argument_text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            args.append(argument_text[start:index].strip())
            start = index + 1
    tail = argument_text[start:].strip()
    if tail:
        args.append(tail)
    return args


def _receiver_tables_from_table_field_alias(
    receiver: str,
    receiver_table_aliases: Mapping[str, Iterable[str]],
    table_field_aliases: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    for receiver_key, key_fn in (
        (_compact_receiver_path(receiver), _compact_receiver_path),
        (_normalize_receiver_path(receiver), _normalize_receiver_path),
    ):
        resolved_tables: list[str] = []
        for alias_receiver, tables in receiver_table_aliases.items():
            alias_key = key_fn(alias_receiver)
            if receiver_key == alias_key:
                continue
            prefix = f"{alias_key}."
            if not receiver_key.startswith(prefix):
                continue
            suffix = receiver_key[len(prefix) :]
            for table in tables:
                resolved = table_field_aliases.get(f"{table}.{suffix}")
                for resolved_table in resolved or ():
                    if resolved_table not in resolved_tables:
                        resolved_tables.append(resolved_table)
        if resolved_tables:
            return tuple(resolved_tables)
    return ()


def _compact_receiver_path(receiver: str) -> str:
    return re.sub(r"\s+", "", receiver).replace("->", ".")


def _normalize_receiver_path(receiver: str) -> str:
    return re.sub(r"\[[^\]]+\]", "", _compact_receiver_path(receiver))


def _unique_table_names(values: Iterable[object]) -> tuple[str, ...]:
    unique: list[str] = []
    for value in values:
        table = str(value)
        if table and table not in unique:
            unique.append(table)
    return tuple(unique)


def _receiver_alias_type_flow(base: str, tables: Iterable[object]) -> str:
    table_names = _unique_table_names(tables)
    return f"{base}_ambiguous" if len(table_names) > 1 else base


def _receiver_table_aliases_for_function(
    function_text: str,
    version_field_sinks: Mapping[str, Iterable[CodeGraphVersionFieldSink]] = {},
    return_table_aliases: Mapping[str, Iterable[str]] = {},
    known_receiver_table_aliases: Mapping[str, Iterable[str]] = {},
) -> tuple[dict[str, list[str]], dict[str, str]]:
    aliases: dict[str, list[str]] = {}
    type_flows: dict[str, str] = {}
    body_open = function_text.find("{")
    if body_open == -1:
        return aliases, type_flows
    table_alias = re.compile(
        r"\b(?P<receiver>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)"
        r"\s*=\s*&?\s*(?P<table>[A-Za-z_]\w*)\s*(?:;|,)"
    )
    returned_table_alias = re.compile(
        r"\b(?P<receiver>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)"
        r"\s*=\s*(?P<callee>[A-Za-z_]\w*)\s*\("
    )
    receiver_alias = re.compile(
        r"\b(?P<receiver>[A-Za-z_]\w*)\s*=\s*&?"
        r"(?P<source>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)"
        r"\s*(?:;|,)"
    )
    for line in function_text[body_open + 1 :].splitlines():
        if "=" not in line:
            continue
        for match in table_alias.finditer(line):
            receiver = re.sub(r"\s+", "", match.group("receiver"))
            table = match.group("table")
            if receiver == table:
                continue
            if not (_looks_like_callback_table_name(table) or table.endswith("_ip_block")):
                continue
            aliases.setdefault(receiver, [])
            if table not in aliases[receiver]:
                aliases[receiver].append(table)
        for match in returned_table_alias.finditer(line):
            receiver = re.sub(r"\s+", "", match.group("receiver"))
            callee = match.group("callee")
            callee_tables = tuple(return_table_aliases.get(callee, ()))
            if len(callee_tables) != 1:
                continue
            for table in callee_tables:
                table_text = str(table)
                if not (_looks_like_callback_table_name(table_text) or table_text.endswith("_ip_block")):
                    continue
                aliases.setdefault(receiver, [])
                if table_text not in aliases[receiver]:
                    aliases[receiver].append(table_text)
                type_flows.setdefault(receiver, "source_return_table_alias")
        visible_receiver_aliases = _merge_table_field_aliases(known_receiver_table_aliases, aliases)
        for match in receiver_alias.finditer(line):
            receiver = re.sub(r"\s+", "", match.group("receiver"))
            source = re.sub(r"\s+", "", match.group("source"))
            if receiver == source:
                continue
            source_tables = _tables_for_receiver_alias(source, visible_receiver_aliases)
            if not source_tables:
                for derived_receiver, derived_tables in _receiver_path_aliases_for_local(
                    receiver,
                    source,
                    visible_receiver_aliases,
                ).items():
                    aliases.setdefault(derived_receiver, [])
                    for table_text in derived_tables:
                        if table_text not in aliases[derived_receiver]:
                            aliases[derived_receiver].append(table_text)
                    type_flows.setdefault(
                        derived_receiver,
                        _receiver_alias_type_flow("local_receiver_path_alias", derived_tables),
                    )
                continue
            aliases.setdefault(receiver, [])
            for table_text in source_tables:
                if table_text not in aliases[receiver]:
                    aliases[receiver].append(table_text)
            type_flows.setdefault(
                receiver,
                _receiver_alias_type_flow("source_receiver_table_alias", source_tables),
            )
    _collect_version_sink_call_aliases(function_text, version_field_sinks, aliases)
    return aliases, type_flows


def _direct_receiver_table_aliases_from_text(source_text: str) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, list[str]] = {}
    assignment = re.compile(
        r"\b(?P<receiver>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)"
        r"\s*=\s*&?\s*(?P<table>[A-Za-z_]\w*)\s*(?:;|,)"
    )
    for line in source_text.splitlines():
        if "=" not in line:
            continue
        for match in assignment.finditer(line):
            receiver = re.sub(r"\s+", "", match.group("receiver"))
            table = match.group("table")
            if receiver == table:
                continue
            if not _is_global_receiver_table_alias(receiver):
                continue
            if not (_looks_like_callback_table_name(table) or table.endswith("_ip_block")):
                continue
            aliases.setdefault(receiver, [])
            if table not in aliases[receiver]:
                aliases[receiver].append(table)
    return {key: tuple(values) for key, values in aliases.items()}


def _is_global_receiver_table_alias(receiver: str) -> bool:
    normalized = _normalize_receiver_path(receiver)
    if "." not in normalized:
        return False
    root = normalized.split(".", 1)[0]
    if root not in {"adev", "adapt"}:
        return False
    leaf = _receiver_leaf(receiver)
    return _looks_like_callback_table_name(leaf)


def _tables_for_receiver_alias(
    receiver: str,
    receiver_table_aliases: Mapping[str, Iterable[str]],
) -> tuple[str, ...]:
    for receiver_key, key_fn in (
        (_compact_receiver_path(receiver), _compact_receiver_path),
        (_normalize_receiver_path(receiver), _normalize_receiver_path),
    ):
        matched_tables: list[str] = []
        for alias_receiver, tables in receiver_table_aliases.items():
            if key_fn(alias_receiver) != receiver_key:
                continue
            for table in tables:
                table_text = str(table)
                if table_text and table_text not in matched_tables:
                    matched_tables.append(table_text)
        if matched_tables:
            return tuple(matched_tables)
    return ()


def _receiver_path_aliases_for_local(
    receiver: str,
    source: str,
    receiver_table_aliases: Mapping[str, Iterable[str]],
) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, list[str]] = {}
    for source_key, key_fn in (
        (_compact_receiver_path(source), _compact_receiver_path),
        (_normalize_receiver_path(source), _normalize_receiver_path),
    ):
        if not source_key:
            continue
        for alias_receiver, tables in receiver_table_aliases.items():
            alias_key = key_fn(alias_receiver)
            if not alias_key.startswith(f"{source_key}."):
                continue
            suffix = alias_key[len(source_key) :]
            derived_receiver = f"{receiver}{suffix.replace('.', '->')}"
            aliases.setdefault(derived_receiver, [])
            for table in tables:
                table_text = str(table)
                if table_text and table_text not in aliases[derived_receiver]:
                    aliases[derived_receiver].append(table_text)
        if aliases:
            break
    return {key: tuple(values) for key, values in aliases.items()}


def _type_flow_for_receiver_alias(receiver: str, type_flows: Mapping[str, str]) -> str:
    normalized_receiver = _normalize_receiver_path(receiver)
    for alias_receiver, type_flow in type_flows.items():
        if not type_flow:
            continue
        normalized_alias = _normalize_receiver_path(alias_receiver)
        if normalized_receiver == normalized_alias or normalized_receiver.startswith(f"{normalized_alias}."):
            return str(type_flow)
    return ""


def _return_table_aliases_from_spans(
    source_text: str,
    spans: Iterable[_FunctionSpan],
) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, list[str]] = {}
    for span in spans:
        function_text = source_text[span.offset_start : span.offset_end + 1]
        body_open = function_text.find("{")
        if body_open == -1:
            continue
        body = function_text[body_open + 1 :]
        for match in re.finditer(r"\breturn\s*&?\s*(?P<table>[A-Za-z_]\w*)\s*;", body):
            table = match.group("table")
            if not (_looks_like_callback_table_name(table) or table.endswith("_ip_block")):
                continue
            aliases.setdefault(span.name, [])
            if table not in aliases[span.name]:
                aliases[span.name].append(table)
    simple_return = re.compile(
        r"\b(?P<function>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{\s*return\s*&?\s*(?P<table>[A-Za-z_]\w*)\s*;",
        re.DOTALL,
    )
    for match in simple_return.finditer(source_text):
        table = match.group("table")
        if not (_looks_like_callback_table_name(table) or table.endswith("_ip_block")):
            continue
        function = match.group("function")
        aliases.setdefault(function, [])
        if table not in aliases[function]:
            aliases[function].append(table)
    return {key: tuple(values) for key, values in aliases.items()}


def _receiver_table_aliases_from_version_sink_calls(
    source_text: str,
    spans: Iterable[_FunctionSpan],
    version_field_sinks: Mapping[str, Iterable[CodeGraphVersionFieldSink]],
) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, list[str]] = {}
    if not version_field_sinks:
        return {}
    for span in spans:
        function_text = source_text[span.offset_start : span.offset_end + 1]
        _collect_version_sink_call_aliases(function_text, version_field_sinks, aliases)
    return {key: tuple(values) for key, values in aliases.items()}


def _collect_version_sink_call_aliases(
    function_text: str,
    version_field_sinks: Mapping[str, Iterable[CodeGraphVersionFieldSink]],
    aliases: dict[str, list[str]],
) -> None:
    if not version_field_sinks:
        return
    for match in re.finditer(r"\b(?P<callee>[A-Za-z_]\w*)\s*\(", function_text):
        callee = match.group("callee")
        sinks = tuple(version_field_sinks.get(callee, ()))
        if not sinks:
            continue
        open_index = match.end() - 1
        close_index = _matching_paren(function_text, open_index)
        if close_index == -1:
            continue
        args = _split_call_arguments(function_text[open_index + 1 : close_index])
        for sink in sinks:
            if sink.target_arg_index >= len(args) or sink.value_arg_index >= len(args):
                continue
            target = _clean_alias_argument(args[sink.target_arg_index])
            value = _clean_alias_argument(args[sink.value_arg_index])
            if not target or not value:
                continue
            if not (value.endswith("_ip_block") or value.endswith("_ip_block_version")):
                continue
            receiver = f"{target}->{sink.target_suffix.replace('.', '->')}"
            aliases.setdefault(receiver, [])
            if value not in aliases[receiver]:
                aliases[receiver].append(value)


def _clean_alias_argument(argument: str) -> str:
    cleaned = argument.strip()
    while cleaned.startswith("&"):
        cleaned = cleaned[1:].strip()
    cleaned = cleaned.strip("() ")
    if re.fullmatch(r"[A-Za-z_]\w*", cleaned):
        return cleaned
    return ""


def _looks_like_callback_table_name(name: str) -> bool:
    return bool(re.search(r"(?:funcs|ops|callbacks|func)$", name))


def _receiver_type_hints_for_function(function_text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    signature_open = function_text.find("(")
    signature_close = _matching_paren(function_text, signature_open) if signature_open != -1 else -1
    if signature_open != -1 and signature_close != -1:
        _collect_receiver_type_hints(function_text[signature_open + 1 : signature_close], hints)
    body_open = function_text.find("{")
    if body_open != -1:
        for line in function_text[body_open + 1 :].splitlines():
            if ";" not in line:
                continue
            _collect_receiver_type_hints(line, hints)
    return hints


def _collect_receiver_type_hints(text: str, hints: dict[str, str]) -> None:
    type_decl = re.compile(
        r"\b(?:const\s+|volatile\s+)*"
        r"(?:struct\s+)?(?P<type>[A-Za-z_]\w*(?:_funcs|_ops|_callbacks|_func))"
        r"\s*\*+\s*(?P<name>[A-Za-z_]\w*)\b"
    )
    for match in type_decl.finditer(text):
        hints.setdefault(match.group("name"), match.group("type"))


def _callbacks_for_slot_call(
    slot_call: CodeGraphSlotCall,
    callbacks_by_slot: Mapping[str, List[CodeGraphCallbackSlot]],
) -> List[CodeGraphCallbackSlot]:
    callbacks = callbacks_by_slot.get(slot_call.slot, [])
    receiver = slot_call.receiver.strip()
    if not receiver:
        return callbacks
    receiver_tables = tuple(str(table) for table in getattr(slot_call, "receiver_tables", ()) if table)
    if receiver_tables:
        exact_alias = [callback for callback in callbacks if callback.table in receiver_tables]
        return exact_alias
    receiver_leaf = _receiver_leaf(receiver)
    exact = [callback for callback in callbacks if callback.table in {receiver, receiver_leaf}]
    if exact:
        return exact
    receiver_type = str(getattr(slot_call, "receiver_type", "") or "").strip()
    if receiver_type:
        typed = [callback for callback in callbacks if callback.table_type == receiver_type]
        return typed
    expected_table_type = _expected_callback_table_type(receiver)
    if expected_table_type:
        typed = [callback for callback in callbacks if callback.table_type == expected_table_type]
        return typed
    if receiver_leaf in _GENERIC_CALLBACK_RECEIVERS:
        return callbacks
    return []


def _callback_call_kind(
    slot_call: CodeGraphSlotCall,
    callbacks: List[CodeGraphCallbackSlot],
) -> str:
    receiver_tables = tuple(str(table) for table in getattr(slot_call, "receiver_tables", ()) if table)
    if len(receiver_tables) == 1:
        return "vtable_table_alias"
    if len(receiver_tables) > 1:
        return "vtable_dispatch"
    receiver_leaf = _receiver_leaf(slot_call.receiver)
    if receiver_leaf in _GENERIC_CALLBACK_RECEIVERS:
        return "vtable_dispatch"
    if len(callbacks) > 1:
        return "vtable_dispatch"
    return "vtable_callback"


def _receiver_leaf(receiver: str) -> str:
    parts = re.split(r"->|\.", receiver.strip())
    leaf = parts[-1] if parts else receiver
    return re.sub(r"\[[^\]]+\]", "", leaf).strip()


def _expected_callback_table_type(receiver: str) -> str:
    normalized = re.sub(r"\s+", "", receiver.strip())
    for suffix, table_type in _CALLBACK_TYPE_BY_RECEIVER_SUFFIX:
        if normalized.endswith(suffix):
            return table_type
    leaf = _receiver_leaf(receiver)
    if leaf in _CALLBACK_TYPE_BY_RECEIVER:
        return _CALLBACK_TYPE_BY_RECEIVER[leaf]
    return ""


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


def _matching_paren(source_text: str, open_index: int) -> int:
    if open_index < 0:
        return -1
    depth = 0
    for index in range(open_index, len(source_text)):
        if source_text[index] == "(":
            depth += 1
        elif source_text[index] == ")":
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
