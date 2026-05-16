"""Live ASIP workbench services backed by SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .documents import convert_pdf_to_chunks
from .providers import EmbeddingProviderConfig, EmbeddingTransport, create_embedding_provider
from .resolver_profiles import (
    ResolverProfile,
    WrapperRule,
    resolve_cpp_register_call,
    resolve_python_symbol,
)
from .semantic_edges import (
    EdgeModelConfig,
    EdgeProvider,
    FullCorpus,
    create_edge_provider,
    load_full_corpus_edge_config,
    normalize_generated_cases,
    scan_full_corpus_queries,
)
from .storage import AsipStore


SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".h", ".hpp", ".md", ".rst", ".txt", ".pdf"}
DEFAULT_CONFIG = Path("configs/edge_cases/full-corpus-qwen35.json")
DEFAULT_DB = Path("data/asip.db")


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: int
    corpus_id: str
    repo: str
    source_type: str
    path: str
    text: str
    line_start: int
    line_end: int
    page: Optional[int] = None


def index_configured_corpora(
    config_path: Path,
    db_path: Path,
    source_roots: Optional[Mapping[str, Path]] = None,
    rebuild: bool = True,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    """Index raw corpus files from a full-corpus config into SQLite."""

    config = load_full_corpus_edge_config(config_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    if rebuild:
        store.reset_index()
    provider_settings = load_provider_settings(db_path)
    job_id = store.start_job(
        "index",
        f"Indexing {config.name}",
        metadata={
            "source": "raw_corpus",
            "config": str(config_path),
            "corpus_ids": [corpus.id for corpus in config.corpora],
            "provider_settings": provider_settings,
        },
    )

    document_count = 0
    chunk_count = 0
    evidence_count = 0
    edge_count = 0

    try:
        actual_source_roots = {
            corpus.id: resolve_corpus_root(corpus, config_path, source_roots or {})
            for corpus in config.corpora
        }
        for corpus in config.corpora:
            source_root = actual_source_roots[corpus.id]
            scan_root = source_root / corpus.relative_root if corpus.relative_root else source_root
            if not scan_root.exists():
                error_message = f"source root not found: {scan_root}"
                store.upsert_corpus(
                    corpus_id=corpus.id,
                    repo=corpus.repo,
                    source_root=str(source_root),
                    include=corpus.include,
                    status="failed",
                    file_count=0,
                    metadata={"relative_root": corpus.relative_root, "scan_root": str(scan_root), "error": error_message},
                )
                raise FileNotFoundError(error_message)
        scan = scan_full_corpus_queries(config, actual_source_roots)
        query_by_id = {query.id: query for query in config.queries}
        document_ids: Dict[tuple[str, str], int] = {}

        for corpus in config.corpora:
            source_root = actual_source_roots[corpus.id]
            corpus_summary = scan["corpora"][corpus.id]
            store.upsert_corpus(
                corpus_id=corpus.id,
                repo=corpus.repo,
                source_root=str(source_root),
                include=corpus.include,
                status="indexing",
                file_count=int(corpus_summary["file_count"]),
                metadata={"relative_root": corpus.relative_root, "scan_root": str(corpus_summary["scan_root"])},
            )

        for query in scan["queries"]:
            corpus_id = str(query["corpus"])
            corpus = next(item for item in config.corpora if item.id == corpus_id)
            query_config = query_by_id[str(query["id"])]
            for snippet in query["snippets"]:
                display_path = str(snippet["path"])
                source_type = _source_type_for_path(Path(display_path))
                if source_type != "code":
                    continue
                key = (corpus_id, display_path)
                if key not in document_ids:
                    document_ids[key] = store.add_document(corpus_id, source_type, display_path)
                    document_count += 1
                page = 1 if source_type == "pdf" else None
                indexed = IndexedChunk(
                    chunk_id=store.add_chunk(
                        document_ids[key],
                        str(snippet["text"]),
                        int(snippet["line_start"]),
                        int(snippet["line_end"]),
                        page=page,
                    ),
                    corpus_id=corpus_id,
                    repo=corpus.repo,
                    source_type=source_type,
                    path=display_path,
                    text=str(snippet["text"]),
                    line_start=int(snippet["line_start"]),
                    line_end=int(snippet["line_end"]),
                    page=page,
                )
                chunk_count += 1
                _index_chunk_embedding(store, indexed, provider_settings, embedding_transport=embedding_transport)
                evidence_count += _index_chunk_evidence(store, indexed, [query_config], _resolver_profiles_from_store(store))
                edge_count += _index_chunk_edges(store, indexed, [query_config])

        indexed_paths = set(document_ids.keys())
        resolver_profiles = _resolver_profiles_from_store(store)
        for corpus in config.corpora:
            source_root = actual_source_roots[corpus.id]
            for file_path in _iter_source_files(source_root, corpus.include):
                display_path = _display_source_path(file_path, source_root, source_root)
                key = (corpus.id, display_path)
                if key in indexed_paths:
                    continue
                source_type = _source_type_for_path(file_path)
                if source_type not in {"doc", "pdf", "register"}:
                    continue
                chunks = _chunks_for_file(file_path, source_type)
                if not chunks:
                    continue
                document_id = store.add_document(corpus.id, source_type, display_path)
                document_count += 1
                indexed_paths.add(key)
                for chunk in chunks:
                    indexed = IndexedChunk(
                        chunk_id=store.add_chunk(
                            document_id,
                            str(chunk["text"]),
                            int(chunk["line_start"]),
                            int(chunk["line_end"]),
                            page=chunk.get("page"),
                        ),
                        corpus_id=corpus.id,
                        repo=corpus.repo,
                        source_type=source_type,
                        path=display_path,
                        text=str(chunk["text"]),
                        line_start=int(chunk["line_start"]),
                        line_end=int(chunk["line_end"]),
                        page=chunk.get("page"),
                    )
                    chunk_count += 1
                    _index_chunk_embedding(store, indexed, provider_settings, embedding_transport=embedding_transport)
                    evidence_count += _index_chunk_evidence(store, indexed, [], resolver_profiles)
                    edge_count += _index_chunk_edges(store, indexed, [])

        for corpus in config.corpora:
            source_root = actual_source_roots[corpus.id]
            corpus_summary = scan["corpora"][corpus.id]
            store.upsert_corpus(
                corpus_id=corpus.id,
                repo=corpus.repo,
                source_root=str(source_root),
                include=corpus.include,
                status="indexed",
                file_count=int(corpus_summary["file_count"]),
                metadata={"relative_root": corpus.relative_root, "scan_root": str(corpus_summary["scan_root"])},
            )
        store.finish_job(job_id, "indexed", f"Indexed {document_count} documents")
    except Exception as exc:
        store.finish_job(job_id, "failed", str(exc))
        raise

    return {
        "source": "raw_corpus",
        "config": config.name,
        "db_path": str(db_path),
        "documents": document_count,
        "chunks": chunk_count,
        "evidence": evidence_count,
        "edges": edge_count,
        "files": int(scan["summary"]["total_files_scanned"]),
        "job_id": job_id,
        "provider_settings": provider_settings,
    }


def query_evidence(
    db_path: Path,
    query: str,
    limit: int = 24,
    ip_block: str = "",
    asic_or_generation: str = "",
) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "evidence"):
        return {
            "query": query,
            "queryId": "",
            "rows": [],
            "graph": {"queryId": "", "nodes": [], "edges": [], "source": "sqlite"},
            "empty": True,
            "empty_state": f"No evidence matched query: {query}",
            "filters": {"ip_block": ip_block, "asic_or_generation": asic_or_generation},
            "source": "sqlite",
        }
    store = AsipStore.connect(str(db_path))
    tokens = _query_tokens(query)
    ip_filter = ip_block.strip().lower()
    asic_filter = asic_or_generation.strip().lower()
    fts_chunk_ids: set[int] = set()
    if tokens:
        try:
            for match in store.search_text(" OR ".join(tokens)):
                fts_chunk_ids.add(int(match["id"]))
        except Exception:
            fts_chunk_ids = set()
    vector_chunk_scores: Dict[int, float] = {}
    if query.strip():
        try:
            for match in store.search_vector(_deterministic_embedding(query), limit=limit):
                vector_score = float(match.get("score") or 0)
                if vector_score >= 0.75:
                    vector_chunk_scores[int(match["chunk_id"])] = vector_score
        except Exception:
            vector_chunk_scores = {}

    candidates = store.all_evidence()
    rows: List[Dict[str, Any]] = []
    for row in candidates:
        if ip_filter and str(row.get("ip_block") or "").lower() != ip_filter:
            continue
        if asic_filter and str(row.get("asic_or_generation") or "").lower() != asic_filter:
            continue
        score = _evidence_score(row, tokens, fts_chunk_ids)
        chunk_id = int(row.get("chunk_id") or 0)
        vector_score = vector_chunk_scores.get(chunk_id, 0.0)
        if score <= 0 and tokens and vector_score <= 0:
            continue
        result = _json_ready(row)
        result["rank_score"] = round(score + float(row.get("confidence") or 0) + (vector_score * 2), 4)
        result["tone"] = _tone_for_source(str(row.get("source_type", "")), str(row.get("entity_type", "")))
        result["source"] = row.get("source_type", "")
        result["score"] = f"{float(row.get('confidence') or 0):.2f}"
        result["relation"] = row.get("access_type", "mention")
        retrieval_sources = []
        if score > 0:
            retrieval_sources.append("lexical")
        if chunk_id in fts_chunk_ids:
            retrieval_sources.append("fts5")
        if vector_score > 0:
            retrieval_sources.append("vector")
            result["vector_score"] = round(vector_score, 4)
        result["retrieval_sources"] = retrieval_sources
        rows.append(result)

    rows.sort(key=lambda item: (-float(item["rank_score"]), str(item["symbol"]), int(item["id"])))
    rows = _select_diverse_rows(_dedupe_rows(rows), limit)
    graph = graph_for_rows(rows, db_path)
    return {
        "query": query,
        "queryId": next((row.get("query_id", "") for row in rows if row.get("query_id")), "") if rows else "",
        "rows": rows,
        "graph": graph,
        "empty": not rows,
        "empty_state": f"No evidence matched query: {query}" if not rows else "",
        "filters": {"ip_block": ip_block, "asic_or_generation": asic_or_generation},
        "source": "sqlite",
    }


def get_evidence_detail(db_path: Path, evidence_id: int) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "evidence"):
        raise ValueError(f"evidence id not found: {evidence_id}")
    store = AsipStore.connect(str(db_path))
    for row in store.all_evidence():
        if int(row["id"]) == int(evidence_id):
            return _json_ready(row)
    raise ValueError(f"evidence id not found: {evidence_id}")


def explain_entity(db_path: Path, symbol: str) -> Dict[str, Any]:
    evidence = query_evidence(db_path, symbol)
    graph = expand_query_graph(db_path, symbol)
    return {
        "symbol": symbol,
        "evidence": evidence.get("rows", []),
        "graph": graph,
        "resolved_chains": [
            row.get("resolved_chain")
            for row in evidence.get("rows", [])
            if row.get("resolved_chain")
        ],
    }


def expand_query_graph(db_path: Path, symbol: str, hops: int = 1) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "edges"):
        return {
            "queryId": symbol,
            "nodes": [_node_with_kind(symbol)],
            "edges": [],
            "source": "networkx",
            "graph_runtime": "networkx",
        }
    store = AsipStore.connect(str(db_path))
    graph = store.expand_graph_networkx(symbol, hops=hops)
    return {
        "queryId": symbol,
        "nodes": [_node_with_kind(node["id"]) for node in graph["nodes"]],
        "edges": [_edge_with_weight(edge) for edge in graph["edges"]],
        "source": "networkx",
        "graph_runtime": graph["graph_runtime"],
    }


def global_graph(db_path: Path, limit: int = 100) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "edges"):
        return {
            "queryId": "global",
            "nodes": [],
            "edges": [],
            "source": "networkx",
            "graph_runtime": "networkx",
        }
    store = AsipStore.connect(str(db_path))
    graph = store.global_graph_networkx(limit=limit)
    return {
        "queryId": "global",
        "nodes": [
            {
                **_node_with_kind(str(node["id"])),
                "weight": node.get("weight", 1),
            }
            for node in graph["nodes"]
        ],
        "edges": [_edge_with_weight(edge) for edge in graph["edges"]],
        "source": "networkx",
        "graph_runtime": graph["graph_runtime"],
    }


def graph_for_rows(rows: List[Dict[str, Any]], db_path: Path) -> Dict[str, Any]:
    if not rows:
        return {"queryId": "", "nodes": [], "edges": [], "source": "sqlite"}
    for row in rows:
        graph = expand_query_graph(db_path, str(row["symbol"]), hops=1)
        if graph["edges"]:
            return graph
    return expand_query_graph(db_path, str(rows[0]["symbol"]), hops=1)


def list_indexed_corpora(db_path: Path, config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    if not _sqlite_table_exists(db_path, "corpora") and config_path:
        config = load_full_corpus_edge_config(config_path)
        return [
            {
                "id": corpus.id,
                "repo": corpus.repo,
                "source_root": str(resolve_corpus_root(corpus, config_path, {})),
                "include": corpus.include,
                "status": "not_indexed",
                "file_count": 0,
                "metadata": {"relative_root": corpus.relative_root},
            }
            for corpus in config.corpora
        ]
    if not _sqlite_table_exists(db_path, "corpora"):
        return []
    store = AsipStore.connect(str(db_path))
    corpora = store.list_corpora()
    if corpora or not config_path:
        return corpora
    config = load_full_corpus_edge_config(config_path)
    return [
        {
            "id": corpus.id,
            "repo": corpus.repo,
            "source_root": str(resolve_corpus_root(corpus, config_path, {})),
            "include": corpus.include,
            "status": "not_indexed",
            "file_count": 0,
            "metadata": {"relative_root": corpus.relative_root},
        }
        for corpus in config.corpora
    ]


def add_corpus(
    db_path: Path,
    corpus_id: str,
    repo: str,
    source_root: str,
    include: Iterable[str],
    corpus_type: str = "code",
) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    store.upsert_corpus(
        corpus_id=corpus_id,
        repo=repo,
        source_root=source_root,
        include=include,
        status="not_indexed",
        file_count=0,
        metadata={"type": corpus_type},
    )
    return {
        "id": corpus_id,
        "repo": repo,
        "source_root": source_root,
        "include": list(include),
        "status": "not_indexed",
        "file_count": 0,
        "metadata": {"type": corpus_type},
    }


def index_registered_corpora(
    db_path: Path,
    corpus_ids: Optional[Iterable[str]] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    corpora = store.list_corpora()
    selected_ids = list(corpus_ids or [str(corpus["id"]) for corpus in corpora])
    selected = [corpus for corpus in corpora if corpus["id"] in selected_ids]
    known_ids = {str(corpus["id"]) for corpus in corpora}
    unknown_ids = [corpus_id for corpus_id in selected_ids if corpus_id not in known_ids]
    provider_settings = load_provider_settings(db_path)
    job_id = store.start_job(
        "index",
        f"Indexing registered corpora: {', '.join(selected_ids)}",
        metadata={
            "source": "registered_corpus",
            "corpus_ids": selected_ids,
            "provider_settings": provider_settings,
        },
    )

    document_count = 0
    chunk_count = 0
    evidence_count = 0
    edge_count = 0
    file_count = 0
    try:
        if unknown_ids:
            raise ValueError(f"unknown corpus id(s): {', '.join(unknown_ids)}")
        if not selected:
            raise ValueError("no registered corpora selected for indexing")
        store.delete_index_for_corpora(selected_ids)
        resolver_profiles = _resolver_profiles_from_store(store)
        for corpus in selected:
            corpus_id = str(corpus["id"])
            source_root = Path(str(corpus["source_root"])).expanduser()
            include = [str(item) for item in corpus["include"]]
            if not source_root.exists():
                error_message = f"source root not found: {source_root}"
                store.upsert_corpus(
                    corpus_id=corpus_id,
                    repo=str(corpus["repo"]),
                    source_root=str(source_root),
                    include=include,
                    status="failed",
                    file_count=0,
                    metadata={**dict(corpus.get("metadata", {})), "error": error_message},
                )
                raise FileNotFoundError(error_message)
            files = list(_iter_source_files(source_root, include))
            file_count += len(files)
            store.upsert_corpus(
                corpus_id=corpus_id,
                repo=str(corpus["repo"]),
                source_root=str(source_root),
                include=include,
                status="indexing",
                file_count=len(files),
                metadata=dict(corpus.get("metadata", {})),
            )
            for file_path in files:
                source_type = _source_type_for_path(file_path)
                chunks = _chunks_for_file(file_path, source_type)
                if not chunks:
                    continue
                display_path = _display_source_path(file_path, source_root, source_root)
                document_id = store.add_document(corpus_id, source_type, display_path)
                document_count += 1
                for chunk in chunks:
                    indexed = IndexedChunk(
                        chunk_id=store.add_chunk(
                            document_id,
                            str(chunk["text"]),
                            int(chunk["line_start"]),
                            int(chunk["line_end"]),
                            page=chunk.get("page"),
                        ),
                        corpus_id=corpus_id,
                        repo=str(corpus["repo"]),
                        source_type=source_type,
                        path=display_path,
                        text=str(chunk["text"]),
                        line_start=int(chunk["line_start"]),
                        line_end=int(chunk["line_end"]),
                        page=chunk.get("page"),
                    )
                    chunk_count += 1
                    _index_chunk_embedding(store, indexed, provider_settings, embedding_transport=embedding_transport)
                    evidence_count += _index_chunk_evidence(store, indexed, [], resolver_profiles)
                    edge_count += _index_chunk_edges(store, indexed, [])
            store.upsert_corpus(
                corpus_id=corpus_id,
                repo=str(corpus["repo"]),
                source_root=str(source_root),
                include=include,
                status="indexed",
                file_count=len(files),
                metadata=dict(corpus.get("metadata", {})),
            )
        store.finish_job(job_id, "indexed", f"Indexed {document_count} documents")
    except Exception as exc:
        store.finish_job(job_id, "failed", str(exc))
        raise

    return {
        "source": "registered_corpus",
        "db_path": str(db_path),
        "corpus_ids": selected_ids,
        "documents": document_count,
        "chunks": chunk_count,
        "evidence": evidence_count,
        "edges": edge_count,
        "files": file_count,
        "job_id": job_id,
        "provider_settings": provider_settings,
    }


def save_provider_settings(db_path: Path, settings: Dict[str, object]) -> Dict[str, object]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    store.save_provider_settings(settings)
    return settings


def load_provider_settings(db_path: Path) -> Dict[str, object]:
    if not _sqlite_table_exists(db_path, "provider_settings"):
        return {}
    store = AsipStore.connect(str(db_path))
    return store.load_provider_settings()


def backfill_provider_embeddings(
    db_path: Path,
    limit: int = 0,
    batch_size: int = 64,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    """Generate provider embeddings for already indexed chunks using current settings."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    provider_settings = load_provider_settings(db_path)
    config = _embedding_provider_config(provider_settings)
    if config is None:
        raise ValueError("embedding provider settings are missing")
    batch_size = max(1, batch_size)
    job_id = store.start_job(
        "embedding_backfill",
        f"Backfilling provider embeddings with {config.provider}:{config.model}",
        metadata={"provider_settings": provider_settings, "limit": limit, "batch_size": batch_size},
    )
    embedded_chunks = 0
    try:
        rows = _chunks_missing_provider_embedding(store, config.provider, config.model, limit=limit)
        provider = create_embedding_provider(config)
        if embedding_transport is not None and hasattr(provider, "transport"):
            provider.transport = embedding_transport
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            vectors = provider.embed([str(row["text"]) for row in batch], config)
            for row, vector in zip(batch, vectors):
                store.add_embedding(
                    int(row["id"]),
                    provider=config.provider,
                    model=config.model,
                    vector=vector,
                    metadata={"source": "provider"},
                )
                embedded_chunks += 1
        store.finish_job(job_id, "embedded", f"Embedded {embedded_chunks} chunks")
    except Exception as exc:
        store.finish_job(job_id, "failed", str(exc))
        raise
    return {
        "source": "provider_embedding_backfill",
        "db_path": str(db_path),
        "provider": config.provider,
        "model": config.model,
        "embedded_chunks": embedded_chunks,
        "batch_size": batch_size,
        "limit": limit,
        "job_id": job_id,
    }


def generate_semantic_edges_for_query(
    db_path: Path,
    query: str,
    limit: int = 8,
    edge_provider: Optional[EdgeProvider] = None,
) -> Dict[str, Any]:
    """Generate semantic edges from indexed evidence rows and persist them to the graph store."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    provider_settings = load_provider_settings(db_path)
    config = _edge_provider_config(provider_settings)
    if config is None:
        raise ValueError("edge provider settings are missing")
    job_id = store.start_job(
        "semantic_edges",
        f"Generating semantic edges for query: {query}",
        metadata={
            "query": query,
            "provider_settings": provider_settings,
        },
    )
    try:
        evidence = query_evidence(db_path, query, limit=limit)
        rows = list(evidence.get("rows", []))
        if not rows:
            raise ValueError(f"no evidence rows matched query: {query}")
        prompt = _semantic_edge_prompt(query, rows)
        provider = edge_provider or create_edge_provider(config)
        generated = normalize_generated_cases(provider.generate(prompt, config))
        edge_count = 0
        for case in generated.get("cases", []):
            if not isinstance(case, Mapping):
                continue
            for edge in case.get("edges", []):
                if not isinstance(edge, Mapping):
                    continue
                src = str(edge.get("src") or "").strip()
                dst = str(edge.get("dst") or "").strip()
                relation = str(edge.get("relation") or "mentions").strip()
                if not src or not dst:
                    continue
                store.add_edge(
                    src=src,
                    dst=dst,
                    relation=relation,
                    confidence=float(edge.get("confidence") or 0.5),
                )
                edge_count += 1
        if edge_count <= 0:
            raise ValueError("semantic edge provider returned no persistable edges")
        store.finish_job(job_id, "generated", f"Generated {edge_count} semantic edges")
    except Exception as exc:
        store.finish_job(job_id, "failed", str(exc))
        raise
    return {
        "source": "semantic_edge_job",
        "db_path": str(db_path),
        "query": query,
        "provider": config.provider,
        "model": config.preferred,
        "evidence_rows": len(rows),
        "edge_count": edge_count,
        "job_id": job_id,
        "graph": graph_for_rows(rows, db_path),
    }


def add_resolver_profile(
    db_path: Path,
    profile_id: str,
    language: str,
    wrappers: Iterable[str],
    strategy: str,
    path: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    wrapper_list = list(wrappers)
    store.upsert_resolver_profile(profile_id, language, wrapper_list, strategy, path, enabled)
    return {
        "id": profile_id,
        "language": language,
        "wrappers": wrapper_list,
        "strategy": strategy,
        "path": path,
        "enabled": enabled,
    }


def list_resolver_profiles(db_path: Path) -> List[Dict[str, Any]]:
    if not _sqlite_table_exists(db_path, "resolver_profiles"):
        return []
    store = AsipStore.connect(str(db_path))
    return store.list_resolver_profiles()


def validate_resolver_profile(db_path: Path, profile_id: str, source: str) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "resolver_profiles"):
        raise KeyError(profile_id)
    store = AsipStore.connect(str(db_path))
    profile_data = store.get_resolver_profile(profile_id)
    language = str(profile_data["language"])
    wrappers = [str(wrapper) for wrapper in profile_data["wrappers"]]
    profile = ResolverProfile(
        id=str(profile_data["id"]),
        language=language,
        wrappers={wrapper: WrapperRule(symbol_arg=0, access=str(profile_data["strategy"])) for wrapper in wrappers},
        python_extractors=wrappers if language == "python" else [],
    )
    resolved = resolve_python_symbol(source, profile) if language == "python" else resolve_cpp_register_call(source, profile)
    symbols = []
    if resolved:
        symbols.append(
            {
                "profile_id": resolved.profile_id,
                "wrapper": resolved.wrapper,
                "symbol": resolved.symbol,
                "access": resolved.access,
            }
        )
    return {"id": profile_id, "valid": bool(symbols), "symbols": symbols}


def resolve_corpus_root(corpus: FullCorpus, config_path: Path, source_roots: Mapping[str, Path]) -> Path:
    if corpus.id in source_roots:
        return source_roots[corpus.id].expanduser()
    env_key = f"ASIP_CORPUS_ROOT_{re.sub(r'[^A-Za-z0-9]+', '_', corpus.id).upper()}"
    if os.environ.get(env_key):
        return Path(str(os.environ[env_key])).expanduser()

    configured = Path(corpus.default_source_root).expanduser()
    if configured.is_absolute() and configured.exists():
        return configured
    repo_relative = (config_path.parents[2] / configured).resolve() if len(config_path.parents) >= 3 else configured
    if repo_relative.exists():
        return repo_relative

    tmp_candidate = Path("/tmp") / f"asip-{corpus.id}"
    if tmp_candidate.exists():
        return tmp_candidate
    if corpus.id == "linux-amdgpu" and Path("/tmp/asip-linux-amdgpu").exists():
        return Path("/tmp/asip-linux-amdgpu")
    return repo_relative


def _chunks_for_file(file_path: Path, source_type: str, queries: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
    terms = _query_terms(queries or [])
    if source_type == "pdf":
        chunks = []
        for chunk in convert_pdf_to_chunks(file_path):
            if terms and not _has_term(chunk.text, terms):
                continue
            chunks.append(
                {
                    "text": chunk.text,
                    "line_start": 1,
                    "line_end": 1,
                    "page": chunk.page,
                }
            )
        return chunks

    text = file_path.read_text(encoding="utf-8", errors="replace")
    if terms and not _has_term(text, terms):
        return []
    lines = text.splitlines()
    if not lines:
        return []
    chunk_size = 80 if source_type == "code" else 40
    chunks = []
    for start in range(0, len(lines), chunk_size):
        selected = lines[start : start + chunk_size]
        body = "\n".join(f"{start + offset + 1}: {line}" for offset, line in enumerate(selected))
        if terms and not _has_term(body, terms):
            continue
        chunks.append({"text": body, "line_start": start + 1, "line_end": start + len(selected)})
    return chunks


def _index_chunk_evidence(
    store: AsipStore,
    chunk: IndexedChunk,
    queries: Iterable[Any],
    resolver_profiles: Optional[Iterable[ResolverProfile]] = None,
) -> int:
    symbols = _evidence_symbols_for_chunk(chunk.text, queries, resolver_profiles or [])
    if not symbols and chunk.source_type in {"doc", "pdf"} and chunk.text.strip():
        symbols = [(_document_anchor_symbol(chunk), "", "mention", f"{chunk.source_type} chunk -> {_document_anchor_symbol(chunk)}")]
    count = 0
    for symbol, query_id, resolved_access, resolved_chain in symbols:
        access_type = resolved_access or _access_type_for_symbol(chunk.text, symbol)
        count += 1
        store.add_evidence(
            chunk_id=chunk.chunk_id,
            corpus_id=chunk.corpus_id,
            source_type=chunk.source_type,
            repo=chunk.repo,
            path=chunk.path,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            page=chunk.page,
            symbol=symbol,
            entity_type=_entity_type_for_source_symbol(chunk.source_type, symbol),
            access_type=access_type,
            confidence=_confidence_for_symbol(chunk.text, symbol),
            snippet=_snippet_for_symbol(chunk.text, symbol),
            resolved_chain=resolved_chain or _resolved_chain_for_symbol(chunk.text, symbol, access_type),
            ip_block=_ip_block_for_symbol(symbol, chunk.path),
            asic_or_generation=_asic_for_path(chunk.path),
            query_id=query_id,
        )
    return count


def _document_anchor_symbol(chunk: IndexedChunk) -> str:
    path = Path(chunk.path)
    if chunk.source_type == "pdf":
        return f"{path.name}#page={chunk.page or 1}"
    return path.name


def _index_chunk_embedding(
    store: AsipStore,
    chunk: IndexedChunk,
    provider_settings: Mapping[str, Any],
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> None:
    config = _embedding_provider_config(provider_settings)
    if config is None:
        return
    try:
        provider = create_embedding_provider(config)
        if embedding_transport is not None and hasattr(provider, "transport"):
            provider.transport = embedding_transport
        vector = provider.embed([chunk.text], config)[0]
        metadata = {"source": "provider"}
    except Exception as exc:
        vector = _deterministic_embedding(chunk.text)
        metadata = {"source": "deterministic-fallback", "error": str(exc)}
    store.add_embedding(
        chunk.chunk_id,
        provider=config.provider,
        model=config.model,
        vector=vector,
        metadata=metadata,
    )


def _embedding_provider_config(provider_settings: Mapping[str, Any]) -> Optional[EmbeddingProviderConfig]:
    embedding = provider_settings.get("embedding") if isinstance(provider_settings, Mapping) else None
    if not isinstance(embedding, Mapping):
        return None
    model = str(embedding.get("model") or embedding.get("embedding_model") or "").strip()
    if not model:
        return None
    edge = provider_settings.get("edge") if isinstance(provider_settings.get("edge"), Mapping) else {}
    headers = embedding.get("extra_headers")
    if not isinstance(headers, Mapping):
        headers = edge.get("extra_headers") if isinstance(edge, Mapping) else {}
    return EmbeddingProviderConfig(
        provider=str(embedding.get("provider") or "ollama"),
        model=model,
        api_base_url=str(embedding.get("api_base_url") or embedding.get("base_url") or "http://localhost:11434"),
        api_path=str(embedding.get("api_path") or ""),
        extra_headers={str(key): str(value) for key, value in dict(headers or {}).items()},
        timeout_seconds=int(embedding.get("timeout_seconds") or (edge.get("timeout_seconds") if isinstance(edge, Mapping) else 60) or 60),
    )


def _edge_provider_config(provider_settings: Mapping[str, Any]) -> Optional[EdgeModelConfig]:
    edge = provider_settings.get("edge") if isinstance(provider_settings, Mapping) else None
    if not isinstance(edge, Mapping):
        return None
    model = str(edge.get("model") or edge.get("preferred") or "").strip()
    if not model:
        return None
    headers = edge.get("extra_headers")
    if not isinstance(headers, Mapping):
        headers = {}
    return EdgeModelConfig(
        preferred=model,
        fallback=str(edge.get("fallback_model") or edge.get("fallback") or ""),
        provider=str(edge.get("provider") or "ollama"),
        api_base_url=str(edge.get("api_base_url") or edge.get("base_url") or "http://localhost:11434"),
        api_path=str(edge.get("api_path") or ""),
        extra_headers={str(key): str(value) for key, value in dict(headers).items()},
        format=str(edge.get("format") or "json"),
        num_ctx=int(edge.get("num_ctx") or 2048),
        num_predict=int(edge.get("num_predict") or 256),
        temperature=float(edge.get("temperature") or 0),
        keep_alive=str(edge.get("keep_alive") or "0s"),
        think=bool(edge.get("think", False)),
        timeout_seconds=int(edge.get("timeout_seconds") or 60),
    )


def _chunks_missing_provider_embedding(
    store: AsipStore,
    provider: str,
    model: str,
    limit: int = 0,
) -> List[Dict[str, Any]]:
    sql = """
        select chunks.id, chunks.text
        from chunks
        left join embeddings
          on embeddings.chunk_id = chunks.id
         and embeddings.provider = ?
         and embeddings.model = ?
        where embeddings.chunk_id is null
        order by chunks.id
    """
    params: List[Any] = [provider, model]
    if limit and limit > 0:
        sql += " limit ?"
        params.append(int(limit))
    return [dict(row) for row in store.con.execute(sql, tuple(params)).fetchall()]


def _semantic_edge_prompt(query: str, rows: Iterable[Mapping[str, Any]]) -> str:
    row_list = list(rows)
    terms = _unique_ordered(
        [
            *[token.upper() for token in _query_tokens(query) if "_" in token or token.isupper()],
            *[str(row.get("symbol") or "") for row in row_list],
        ]
    )
    snippet_lines = []
    for index, row in enumerate(row_list, start=1):
        path = row.get("path") or "unknown"
        line_start = row.get("line_start") or row.get("page") or 1
        snippet = str(row.get("snippet") or row.get("resolved_chain") or row.get("symbol") or "")
        snippet_lines.append(f"{index}: {path}:{line_start}: {snippet}")
    return "\n".join(
        [
            "CASE workbench-query",
            f"TERMS: {', '.join(term for term in terms if term)}",
            "SNIPPET:",
            *snippet_lines,
        ]
    )


def _index_chunk_edges(store: AsipStore, chunk: IndexedChunk, queries: Iterable[Any]) -> int:
    count = 0
    for query in queries:
        terms = [term for term in query.expected_terms if term in chunk.text]
        if len(terms) < 2:
            continue
        for src, dst in zip(terms, terms[1:]):
            store.add_edge(src=src, dst=dst, relation=_relation_for_terms(chunk.text, src, dst), confidence=0.9)
            count += 1
    return count


def _iter_source_files(root: Path, include: Iterable[str]) -> Iterable[Path]:
    if not root.exists():
        return []
    files: List[Path] = []
    patterns = tuple(include) or ("**/*.c", "**/*.h")
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(root).as_posix()
        if _matches_include(relative, patterns):
            files.append(path)
    return sorted(files)


def _matches_include(relative_path: str, include: Iterable[str]) -> bool:
    path = PurePosixPath(relative_path)
    for pattern in include:
        normalized = pattern.replace("\\", "/")
        if path.match(normalized):
            return True
        if normalized.startswith("**/") and path.match(normalized[3:]):
            return True
    return False


def _unique_ordered(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _evidence_symbols_for_chunk(
    text: str,
    queries: Iterable[Any],
    resolver_profiles: Iterable[ResolverProfile],
) -> List[tuple[str, str, Optional[str], Optional[str]]]:
    found: Dict[str, tuple[str, Optional[str], Optional[str]]] = {}
    for query in queries:
        for term in query.expected_terms:
            if term in text:
                found[term] = (query.id, None, None)
    for identifier in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:->[A-Za-z_][A-Za-z0-9_]*)?\b", text):
        if _is_symbol_like(identifier):
            found.setdefault(identifier, ("", None, None))
    for profile in resolver_profiles:
        resolved = resolve_python_symbol(text, profile) if profile.language == "python" else resolve_cpp_register_call(text, profile)
        if resolved:
            found[resolved.symbol] = (
                "",
                resolved.access,
                f"resolver profile {resolved.profile_id} -> {resolved.wrapper} -> {resolved.symbol}",
            )
    return [(symbol, *values) for symbol, values in sorted(found.items())]


def _resolver_profiles_from_store(store: AsipStore) -> List[ResolverProfile]:
    profiles = []
    for row in store.list_resolver_profiles():
        if not row.get("enabled", True):
            continue
        wrappers = [str(wrapper) for wrapper in row.get("wrappers", [])]
        language = str(row.get("language") or "cpp")
        access = str(row.get("strategy") or "reference")
        profiles.append(
            ResolverProfile(
                id=str(row["id"]),
                language=language,
                wrappers={wrapper: WrapperRule(symbol_arg=0, access=access) for wrapper in wrappers},
                python_extractors=wrappers if language == "python" else [],
            )
        )
    return profiles


def _deterministic_embedding(text: str) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    return [round((digest[index] / 255.0) * 2 - 1, 6) for index in range(8)]


def _query_terms(queries: Iterable[Any]) -> List[str]:
    terms: List[str] = []
    for query in queries:
        terms.extend(query.terms)
        terms.extend(query.expected_terms)
        for term in [*query.terms, *query.expected_terms]:
            terms.extend(part for part in re.split(r"[^A-Za-z0-9]+", term) if len(part) > 2)
    return sorted(set(terms), key=len, reverse=True)


def _has_term(text: str, terms: Iterable[str]) -> bool:
    lower_text = text.lower()
    return any(term in text or term.lower() in lower_text for term in terms)


def _is_symbol_like(identifier: str) -> bool:
    if identifier in {"static", "void", "uint32_t", "return", "data"}:
        return False
    return "_" in identifier or identifier.startswith(("reg", "mm")) or identifier.isupper()


def _source_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    normalized = path.as_posix().lower()
    name = path.name.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".rst", ".txt"}:
        return "doc"
    if suffix == ".h" and (
        "/asic_reg/" in normalized
        or "/register" in normalized
        or name.endswith("_offset.h")
        or name.endswith("_sh_mask.h")
        or name.endswith("_d.h")
    ):
        return "register"
    return "code"


def _entity_type_for_symbol(symbol: str) -> str:
    if "->" in symbol:
        return "context"
    if re.search(r"ENABLE|DISABLE|PENDING|MASK|SHIFT|RESET_REQUEST|INVALIDATE", symbol):
        return "field"
    if symbol.startswith(("WREG", "RREG", "REG_")):
        return "macro"
    if symbol.startswith(("reg", "mm")) or re.search(r"CNTL|STATUS|RESET|BASE|SIZE|VMID|DOORBELL", symbol):
        return "register"
    return "function"


def _entity_type_for_source_symbol(source_type: str, symbol: str) -> str:
    if source_type == "pdf":
        return "pdf_page"
    if source_type == "doc":
        return "doc_section"
    return _entity_type_for_symbol(symbol)


def _access_type_for_symbol(text: str, symbol: str) -> str:
    if f"REG_SET_FIELD" in text and symbol in text:
        return "field_set" if _entity_type_for_symbol(symbol) == "field" else "read_modify_write"
    if re.search(rf"\bWREG[0-9A-Z_]*\s*\([^)]*{re.escape(symbol)}", text):
        return "write"
    if re.search(rf"\bRREG[0-9A-Z_]*\s*\([^)]*{re.escape(symbol)}", text):
        return "read"
    return "mention"


def _confidence_for_symbol(text: str, symbol: str) -> float:
    return 0.95 if re.search(rf"\b{re.escape(symbol)}\b", text) else 0.75


def _resolved_chain_for_symbol(text: str, symbol: str, access_type: str) -> str:
    if "REG_SET_FIELD" in text:
        match = re.search(r"REG_SET_FIELD\s*\(([^)]*)\)", text, flags=re.DOTALL)
        if match:
            args = [part.strip() for part in match.group(1).split(",")]
            if len(args) >= 4:
                return f"REG_SET_FIELD -> register {args[1]} -> field {args[2]} -> {symbol}"
    if access_type in {"read", "write"}:
        return f"{access_type} wrapper -> {symbol}"
    return f"source mention -> {symbol}"


def _relation_for_terms(text: str, src: str, dst: str) -> str:
    if "REG_SET_FIELD" in text and _entity_type_for_symbol(dst) == "field":
        return "sets_field"
    if "reg_offset" in text or "BASE" in dst:
        return "maps_base"
    if re.search(r"\bWREG", text):
        return "writes"
    if re.search(r"\bRREG", text):
        return "reads"
    return "mentions"


def _snippet_for_symbol(text: str, symbol: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if symbol in line:
            start = max(0, index - 2)
            end = min(len(lines), index + 3)
            return "\n".join(lines[start:end])
    return "\n".join(lines[:5])


def _query_tokens(query: str) -> List[str]:
    stop_words = {"which", "what", "where", "show", "the", "and", "for", "with", "before", "who", "write", "writes", "read", "reads"}
    return [
        token
        for token in re.split(r"[^A-Za-z0-9_]+", query.lower())
        if len(token) > 2 and token not in stop_words
    ]


def _evidence_score(row: Dict[str, object], tokens: List[str], fts_chunk_ids: set[int]) -> float:
    if not tokens:
        return 1.0
    haystack = " ".join(str(row.get(key, "")) for key in ("symbol", "path", "snippet", "resolved_chain")).lower()
    symbol_haystack = str(row.get("symbol", "")).lower()
    token_hits = sum(1 for token in tokens if token in haystack)
    symbol_hits = sum(1 for token in tokens if token in symbol_haystack)
    fts_hit = 2 if int(row.get("chunk_id") or 0) in fts_chunk_ids else 0
    if token_hits == 0 and fts_hit == 0:
        return 0.0
    code_priority = 1.0 if row.get("source_type") == "code" else 0.0
    access_priority = 1.0 if row.get("access_type") in {"field_set", "write", "read_modify_write"} else 0.0
    return token_hits + (symbol_hits * 3) + fts_hit + code_priority + access_priority


def _dedupe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[tuple[Any, Any, Any], Dict[str, Any]] = {}
    for row in rows:
        key = (row["symbol"], row["path"], row.get("page") or row.get("line_start"))
        deduped.setdefault(key, row)
    return list(deduped.values())


def _select_diverse_rows(rows: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    selected = rows[:limit]
    selected_ids = {row.get("id") for row in selected}
    protected_ids = {
        row.get("id")
        for row in selected
        if str(row.get("source_type") or row.get("source") or "") in {"register", "doc", "pdf"}
    }
    selected_sources = {str(row.get("source_type") or row.get("source") or "") for row in selected}
    for source_type in ("register", "doc", "pdf"):
        if source_type in selected_sources:
            continue
        candidate = next(
            (
                row
                for row in rows
                if str(row.get("source_type") or row.get("source") or "") == source_type
                and row.get("id") not in selected_ids
            ),
            None,
        )
        if candidate is None:
            continue
        if len(selected) < limit:
            selected.append(candidate)
        else:
            replace_index = next(
                (
                    index
                    for index in range(len(selected) - 1, -1, -1)
                    if selected[index].get("id") not in protected_ids
                ),
                len(selected) - 1,
            )
            selected[replace_index] = candidate
        selected_ids = {row.get("id") for row in selected}
        protected_ids.add(candidate.get("id"))
        selected_sources.add(source_type)
    return selected


def _json_ready(row: Dict[str, object]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if value is not None
    }


def _edge_with_weight(edge: Dict[str, object]) -> Dict[str, Any]:
    result = dict(edge)
    result["weight"] = float(edge.get("confidence") or 0)
    return result


def _node_with_kind(node_id: str) -> Dict[str, Any]:
    return {"id": node_id, "kind": _entity_type_for_symbol(node_id), "weight": 1}


def _tone_for_source(source_type: str, entity_type: str) -> str:
    if source_type == "pdf":
        return "pdf"
    if source_type == "doc":
        return "doc"
    if entity_type in {"register", "macro"}:
        return "register"
    if entity_type == "field":
        return "success"
    return "code"


def _ip_block_for_symbol(symbol: str, path: str) -> str:
    upper = f"{symbol} {path}".upper()
    for candidate in ("GC", "CP", "SDMA", "GMC", "BIF", "RLC", "GDS"):
        if candidate in upper:
            return candidate
    return ""


def _asic_for_path(path: str) -> str:
    match = re.search(r"(gfx|gc|nbio|sdma)[_/.-]?v?(\d+[_\.]\d+|\d+)", path, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def _display_source_path(file_path: Path, source_root: Path, scan_root: Path) -> str:
    try:
        return str(file_path.relative_to(source_root))
    except ValueError:
        try:
            return str(file_path.relative_to(scan_root))
        except ValueError:
            return str(file_path)


def _sqlite_table_exists(db_path: Path, table_name: str) -> bool:
    if not db_path.exists():
        return False
    con = None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = con.execute(
            "select count(*) from sqlite_master where type='table' and name=?",
            (table_name,),
        ).fetchone()
        return bool(row and int(row[0]) > 0)
    except sqlite3.DatabaseError:
        return False
    finally:
        if con is not None:
            con.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="asip.workbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    index_parser.add_argument("--db", default=str(DEFAULT_DB))

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--db", default=str(DEFAULT_DB))
    query_parser.add_argument("--q", required=True)
    query_parser.add_argument("--ip-block", default="")
    query_parser.add_argument("--asic", default="")

    graph_parser = subparsers.add_parser("graph")
    graph_parser.add_argument("--db", default=str(DEFAULT_DB))
    graph_parser.add_argument("--symbol")
    graph_parser.add_argument("--hops", type=int, default=1)
    graph_parser.add_argument("--limit", type=int, default=100)

    corpora_parser = subparsers.add_parser("corpora")
    corpora_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    corpora_parser.add_argument("--db", default=str(DEFAULT_DB))

    corpus_add_parser = subparsers.add_parser("corpus-add")
    corpus_add_parser.add_argument("--db", default=str(DEFAULT_DB))
    corpus_add_parser.add_argument("--id", required=True)
    corpus_add_parser.add_argument("--repo", default="local")
    corpus_add_parser.add_argument("--source-root", required=True)
    corpus_add_parser.add_argument("--include", action="append", default=[])
    corpus_add_parser.add_argument("--type", default="code")

    args = parser.parse_args(argv)
    if args.command == "index":
        payload = index_configured_corpora(Path(args.config), Path(args.db))
    elif args.command == "query":
        payload = query_evidence(Path(args.db), args.q, ip_block=args.ip_block, asic_or_generation=args.asic)
    elif args.command == "graph":
        payload = expand_query_graph(Path(args.db), args.symbol, hops=args.hops) if args.symbol else global_graph(Path(args.db), limit=args.limit)
    elif args.command == "corpora":
        payload = {"corpora": list_indexed_corpora(Path(args.db), Path(args.config))}
    elif args.command == "corpus-add":
        payload = add_corpus(
            Path(args.db),
            corpus_id=args.id,
            repo=args.repo,
            source_root=args.source_root,
            include=args.include or ["**/*"],
            corpus_type=args.type,
        )
    else:  # pragma: no cover
        raise ValueError(args.command)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
