#!/usr/bin/env python3
"""Audit callback/vtable graph edges in a built ASIP SQLite database."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


CONTROL_KEYWORDS = {
    "case",
    "default",
    "do",
    "else",
    "for",
    "if",
    "return",
    "switch",
    "while",
}
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--assert-no-parser-pollution", action="store_true")
    parser.add_argument(
        "--max-ambiguous-fanout",
        type=int,
        help="Maximum allowed unexplained ambiguous callback fanout per caller.",
    )
    parser.add_argument(
        "--require-real-oracle",
        action="append",
        default=[],
        metavar="PATH:FUNCTION",
        help="Require at least one callback/vtable edge from FUNCTION in PATH.",
    )
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args(argv)

    artifact = run_audit(
        args.db,
        assert_no_parser_pollution=args.assert_no_parser_pollution,
        max_ambiguous_fanout=args.max_ambiguous_fanout,
        real_oracles=args.require_real_oracle,
    )
    text = json.dumps(artifact, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(f"{text}\n", encoding="utf-8")
    print(text)
    if artifact["gate_status"] != "pass" and not args.allow_blocked:
        return 1
    return 0


def run_audit(
    db_path: Path,
    *,
    assert_no_parser_pollution: bool = False,
    max_ambiguous_fanout: int | None = None,
    real_oracles: Iterable[str] = (),
) -> Dict[str, Any]:
    failures: List[str] = []
    edges = _load_callback_edges(db_path)
    call_kind_counts = Counter(str(edge["provenance"].get("call_kind") or "unknown") for edge in edges)
    type_flow_counts = Counter(str(edge["provenance"].get("type_flow") or "") for edge in edges)
    dispatch_scope_counts = Counter(str(edge["provenance"].get("dispatch_scope") or "") for edge in edges)
    ambiguous_by_src: Dict[str, int] = defaultdict(int)
    unexplained_ambiguous_by_src: Dict[str, int] = defaultdict(int)
    explained_dynamic_by_src: Dict[str, int] = defaultdict(int)
    for edge in edges:
        if _is_ambiguous_callback(edge["provenance"]):
            ambiguous_by_src[str(edge["src"])] += 1
            if _is_explainable_dynamic_dispatch(edge["provenance"]):
                explained_dynamic_by_src[str(edge["src"])] += 1
            else:
                unexplained_ambiguous_by_src[str(edge["src"])] += 1
    top_ambiguous_fanout = [
        {"src": src, "ambiguous_edge_count": count}
        for src, count in sorted(ambiguous_by_src.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    top_unexplained_ambiguous_fanout = [
        {"src": src, "ambiguous_edge_count": count}
        for src, count in sorted(unexplained_ambiguous_by_src.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    top_explained_dynamic_fanout = [
        {"src": src, "dynamic_edge_count": count}
        for src, count in sorted(explained_dynamic_by_src.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]

    pollution_samples: List[Dict[str, Any]] = []
    if assert_no_parser_pollution:
        pollution_samples = _parser_pollution_samples(edges)
        if pollution_samples:
            failures.append(f"parser pollution candidates found: {len(pollution_samples)}")

    if max_ambiguous_fanout is not None:
        excessive = [
            item
            for item in top_unexplained_ambiguous_fanout
            if item["ambiguous_edge_count"] > max_ambiguous_fanout
        ]
        if excessive:
            worst = excessive[0]
            failures.append(
                f"unexplained ambiguous callback fanout exceeds {max_ambiguous_fanout}: "
                f"{worst['src']} has {worst['ambiguous_edge_count']} ambiguous edges"
            )

    oracle_results = [_real_oracle_result(edges, oracle) for oracle in real_oracles]
    for result in oracle_results:
        if result["status"] != "pass":
            failures.append(str(result["message"]))

    return {
        "source": "asip.callback_edge_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "ambiguous_fanout_limit_scope": "unexplained_ambiguous_only",
        "gate_status": "pass" if not failures else "blocked",
        "failure_reasons": failures,
        "summary": {
            "callback_edge_count": len(edges),
            "ambiguous_callback_edge_count": sum(ambiguous_by_src.values()),
            "explained_dynamic_dispatch_edge_count": sum(explained_dynamic_by_src.values()),
            "unexplained_ambiguous_callback_edge_count": sum(unexplained_ambiguous_by_src.values()),
            "unique_ambiguous_callers": len(ambiguous_by_src),
            "unique_unexplained_ambiguous_callers": len(unexplained_ambiguous_by_src),
            "parser_pollution_candidate_count": len(pollution_samples),
            "real_oracle_total": len(oracle_results),
            "real_oracle_passed": sum(1 for item in oracle_results if item["status"] == "pass"),
        },
        "call_kind_counts": dict(sorted(call_kind_counts.items())),
        "type_flow_counts": dict(sorted(type_flow_counts.items())),
        "dispatch_scope_counts": dict(sorted(dispatch_scope_counts.items())),
        "top_ambiguous_fanout": top_ambiguous_fanout,
        "top_explained_dynamic_fanout": top_explained_dynamic_fanout,
        "top_unexplained_ambiguous_fanout": top_unexplained_ambiguous_fanout,
        "parser_pollution_samples": pollution_samples[:20],
        "real_oracles": oracle_results,
    }


def _load_callback_edges(db_path: Path) -> List[Dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    rows: List[Dict[str, Any]] = []
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            """
            select id, src, dst, relation, path, line_start, line_end, provenance_json
            from edges
            where provenance_json like '%vtable%'
               or provenance_json like '%callback%'
               or provenance_json like '%receiver_tables%'
            order by id
            """
        ):
            provenance = _parse_json(row["provenance_json"])
            if not _is_callback_provenance(provenance):
                continue
            rows.append(
                {
                    "id": row["id"],
                    "src": row["src"],
                    "dst": row["dst"],
                    "relation": row["relation"],
                    "path": row["path"],
                    "line_start": row["line_start"],
                    "line_end": row["line_end"],
                    "provenance": provenance,
                }
            )
    return rows


def _parse_json(text: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, Mapping) else {}


def _is_callback_provenance(provenance: Mapping[str, Any]) -> bool:
    call_kind = str(provenance.get("call_kind") or "")
    if call_kind.startswith("vtable_") or "callback" in call_kind:
        return True
    return bool(provenance.get("receiver_tables") or provenance.get("callback_table"))


def _is_ambiguous_callback(provenance: Mapping[str, Any]) -> bool:
    if provenance.get("callback_ambiguous") is True:
        return True
    dispatch_scope = str(provenance.get("dispatch_scope") or "")
    type_flow = str(provenance.get("type_flow") or "")
    return "ambiguous" in dispatch_scope or "ambiguous" in type_flow or type_flow == "generic_slot"


def _is_explainable_dynamic_dispatch(provenance: Mapping[str, Any]) -> bool:
    receiver = str(provenance.get("receiver") or "")
    receiver_type = str(provenance.get("receiver_type") or "")
    receiver_tables = provenance.get("receiver_tables")
    type_flow = str(provenance.get("type_flow") or "")
    if isinstance(receiver_tables, list) and len(receiver_tables) > 1:
        return True
    if (
        ("->version->funcs" in receiver or ".version->funcs" in receiver or ".version.funcs" in receiver)
        and str(provenance.get("callback_table_type") or "") == "amd_ip_funcs"
    ):
        return True
    if "[" in receiver and receiver_type.endswith(("_funcs", "_ops", "_callbacks", "_func")):
        return True
    if receiver in {"src->funcs", "src.funcs"} and receiver_type.endswith(("_funcs", "_ops", "_callbacks", "_func")):
        return True
    if receiver.strip() == "init_func" and receiver_type == "amdgv_init_func" and type_flow == "clang_ast_json":
        return True
    if (
        type_flow == "clang_ast_json"
        and receiver_type
        and receiver_type == str(provenance.get("callback_table_type") or "")
        and int(provenance.get("callback_candidate_count") or 0) > 1
    ):
        return True
    if (
        receiver
        and receiver_type
        and receiver_type == str(provenance.get("callback_table_type") or "")
        and receiver_type.endswith(("_funcs", "_ops", "_callbacks", "_func"))
        and provenance.get("callback_table")
        and int(provenance.get("callback_candidate_count") or 0) > 1
    ):
        return True
    return False


def _parser_pollution_samples(edges: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for edge in edges:
        provenance = edge["provenance"]
        for field, value in (
            ("src", edge.get("src")),
            ("dst", edge.get("dst")),
            ("function", provenance.get("function")),
            ("callee", provenance.get("callee")),
        ):
            symbol = str(value or "")
            if not symbol:
                continue
            reason = _symbol_pollution_reason(symbol)
            if reason:
                samples.append(
                    {
                        "edge_id": edge.get("id"),
                        "field": field,
                        "symbol": symbol,
                        "reason": reason,
                        "path": edge.get("path"),
                        "line_start": edge.get("line_start"),
                    }
                )
                break
    return samples


def _symbol_pollution_reason(symbol: str) -> str:
    lowered = symbol.strip().lower()
    if lowered in CONTROL_KEYWORDS:
        return "control keyword"
    if "else if" in lowered or lowered.endswith(".if") or lowered.endswith(".else"):
        return "control-flow text parsed as function"
    if not IDENTIFIER_RE.match(symbol):
        return "not a C identifier"
    return ""


def _real_oracle_result(edges: List[Mapping[str, Any]], oracle: str) -> Dict[str, Any]:
    if ":" not in oracle:
        return {"oracle": oracle, "status": "fail", "message": "oracle must use PATH:FUNCTION"}
    oracle_path, function = oracle.rsplit(":", 1)
    matches = [
        edge
        for edge in edges
        if str(edge.get("path") or "").endswith(oracle_path)
        and (
            edge.get("src") == function
            or edge["provenance"].get("function") == function
        )
    ]
    if not matches:
        return {
            "oracle": oracle,
            "status": "fail",
            "message": f"real oracle has no callback/vtable edge: {oracle}",
            "match_count": 0,
        }
    return {
        "oracle": oracle,
        "status": "pass",
        "message": "ok",
        "match_count": len(matches),
        "sample": {
            "src": matches[0].get("src"),
            "dst": matches[0].get("dst"),
            "path": matches[0].get("path"),
            "line_start": matches[0].get("line_start"),
            "call_kind": matches[0]["provenance"].get("call_kind"),
            "type_flow": matches[0]["provenance"].get("type_flow"),
        },
    }


if __name__ == "__main__":
    sys.exit(main())
