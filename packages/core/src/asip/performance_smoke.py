"""Repeatable performance smoke checks for ASIP fixture indexing and query."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

from .storage import AsipStore
from .workbench import index_registered_corpora, query_evidence


DEFAULT_FIXTURE_QUERIES = (
    "GCVM_L2_CNTL",
    "IH_RB_CNTL",
    "SDMA0_QUEUE0_RB_CNTL",
    "program_gcvm_l2",
    "interrupt ring buffer",
)


def run_fixture_performance_smoke(
    db_path: Path,
    *,
    source_root: Path,
    queries: Optional[Iterable[str]] = None,
    corpus_id: str = "fixture-performance",
    query_limit: int = 8,
    max_query_seconds: float = 1.0,
) -> Mapping[str, Any]:
    """Index the same fixture twice from empty DBs and time live queries.

    This is intentionally a small deterministic smoke. It proves the rebuild
    path can start from an empty SQLite file, produce stable counts, and answer
    multiple live queries within a local threshold.
    """

    requested_queries = [query.strip() for query in (queries or DEFAULT_FIXTURE_QUERIES) if query.strip()]
    if not requested_queries:
        raise ValueError("at least one performance smoke query is required")
    source_root = source_root.expanduser()
    if not source_root.exists():
        raise FileNotFoundError(f"source root not found: {source_root}")

    primary_db = db_path.expanduser()
    repeat_db = _repeat_db_path(primary_db)
    runs = [
        _run_single_fixture_index(primary_db, source_root, corpus_id),
        _run_single_fixture_index(repeat_db, source_root, corpus_id),
    ]
    deterministic_counts_match = runs[0]["counts"] == runs[1]["counts"]
    query_timings = _time_queries(primary_db, requested_queries, query_limit, max_query_seconds)
    return {
        "source": "fixture_performance_smoke",
        "db_path": str(primary_db),
        "repeat_db_path": str(repeat_db),
        "source_root": str(source_root),
        "corpus_id": corpus_id,
        "deterministic_counts_match": deterministic_counts_match,
        "runs": runs,
        "queries": query_timings,
        "max_query_seconds": max_query_seconds,
        "all_queries_under_threshold": all(item["elapsed_seconds"] <= max_query_seconds for item in query_timings),
    }


def _run_single_fixture_index(db_path: Path, source_root: Path, corpus_id: str) -> Mapping[str, Any]:
    _remove_sqlite_files(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    store.upsert_corpus(
        corpus_id,
        "local-fixture",
        str(source_root),
        ["**/*.c", "**/*.h", "**/*.md", "**/*.rst", "**/*.txt", "**/*.pdf"],
        status="not_indexed",
        file_count=0,
    )
    started = time.perf_counter()
    summary = index_registered_corpora(db_path, corpus_ids=[corpus_id])
    elapsed = time.perf_counter() - started
    return {
        "db_path": str(db_path),
        "elapsed_seconds": round(elapsed, 6),
        "counts": _db_counts(db_path),
        "index_summary": {
            "documents": int(summary.get("documents") or 0),
            "chunks": int(summary.get("chunks") or 0),
            "evidence": int(summary.get("evidence") or 0),
            "edges": int(summary.get("edges") or 0),
            "files": int(summary.get("files") or 0),
        },
    }


def _time_queries(
    db_path: Path,
    queries: Iterable[str],
    query_limit: int,
    max_query_seconds: float,
) -> List[Mapping[str, Any]]:
    timings: List[Mapping[str, Any]] = []
    for query in queries:
        started = time.perf_counter()
        result = query_evidence(db_path, query, limit=query_limit)
        elapsed = time.perf_counter() - started
        graph = result.get("graph") if isinstance(result.get("graph"), Mapping) else {}
        timings.append(
            {
                "query": query,
                "elapsed_seconds": round(elapsed, 6),
                "under_threshold": elapsed <= max_query_seconds,
                "row_count": len(result.get("rows") or []),
                "graph_nodes": len(graph.get("nodes") or []),
                "graph_edges": len(graph.get("edges") or []),
                "graph_runtime": str(graph.get("graph_runtime") or graph.get("source") or ""),
            }
        )
    return timings


def _db_counts(db_path: Path) -> Mapping[str, int]:
    store = AsipStore.connect(str(db_path))
    counts: dict[str, int] = {}
    for table in ("corpora", "documents", "chunks", "evidence", "edges", "embeddings", "jobs"):
        row = store.con.execute(f"select count(*) as count from {table}").fetchone()
        counts[table] = int(row["count"] if row is not None else 0)
    return counts


def _repeat_db_path(db_path: Path) -> Path:
    suffix = "".join(db_path.suffixes)
    if suffix:
        return db_path.with_name(f"{db_path.name.removesuffix(suffix)}-repeat{suffix}")
    return db_path.with_name(f"{db_path.name}-repeat")


def _remove_sqlite_files(db_path: Path) -> None:
    for candidate in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass
