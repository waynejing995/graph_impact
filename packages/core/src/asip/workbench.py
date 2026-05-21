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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .code_graph import (
    CodeGraphFunctionLocation,
    CodeGraphVersionFieldSink,
    build_deterministic_code_graph,
    collect_code_graph_function_locations,
    collect_code_graph_receiver_table_aliases,
    collect_code_graph_return_table_aliases,
    collect_code_graph_table_field_aliases,
    collect_code_graph_version_field_sinks,
)
from .documents import convert_pdf_to_chunks
from .graph_filters import is_graph_entity_endpoint, is_resolver_wrapper_name
from .graph_schema import normalize_product_relation, product_endpoint_kind
from .limits import DEFAULT_WORKBENCH_LIMITS_PATH, load_workbench_limits
from .providers import EmbeddingProviderConfig, EmbeddingTransport, create_embedding_provider
from .resolver_profiles import (
    ResolverProfile,
    load_resolver_profile,
    load_resolver_profiles,
    resolve_cpp_register_calls,
    resolve_python_symbol,
    resolver_profile_from_config,
    resolver_profile_to_config,
)
from .semantic_edges import (
    EdgeModelConfig,
    EdgeProvider,
    FullCorpus,
    create_doc_node_provider,
    create_edge_provider,
    full_corpus_scan_folders,
    load_full_corpus_edge_config,
    normalize_corpus_relative_root,
    normalize_generated_cases,
    scan_full_corpus_queries,
)
from .storage import AsipStore, section_overlay_graph_for_evidence_rows


SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".h", ".hpp", ".md", ".rst", ".txt", ".pdf"}
DEFAULT_CONFIG = Path("configs/edge_cases/full-corpus-gemma4-e4b.json")
DEFAULT_DB = Path("data/asip.db")
DEFAULT_RESOLVER_PROFILE_DIR = Path(__file__).resolve().parents[4] / "configs" / "resolvers"
GENERIC_CALLBACK_RECEIVERS = {"funcs", "ops", "callbacks", "init_func", "init_funcs"}
DOC_NODE_PROMPT_TEXT_CHARS = 900
DOC_NODE_PROMPT_TERM_LIMIT = 12
DOC_NODE_MAX_BATCH_SIZE = 2
DOC_NODE_MULTI_BATCH_MIN_CTX = 4096
DOC_NODE_MULTI_BATCH_MIN_PREDICT = 1536
CALLBACK_TYPE_BY_RECEIVER = {
    "funcs": "amd_ip_funcs",
    "init_func": "amdgv_init_func",
    "init_funcs": "amdgv_init_func",
}
CALLBACK_TYPE_BY_RECEIVER_SUFFIX = (
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


@dataclass(frozen=True)
class CorpusScanFolder:
    relative_root: str
    include: List[str]
    scan_root: Path


def index_configured_corpora(
    config_path: Path,
    db_path: Path,
    source_roots: Optional[Mapping[str, Path]] = None,
    rebuild: bool = True,
    embedding_transport: Optional[EmbeddingTransport] = None,
    resolver_profile_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Index raw corpus files from a full-corpus config into SQLite."""

    config = load_full_corpus_edge_config(config_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    if rebuild:
        store.reset_index()
    provider_settings = load_provider_settings(db_path)
    requested_resolver_profile_ids = _normal_resolver_profile_ids(resolver_profile_ids)
    job_id = store.start_job(
        "index",
        f"Indexing {config.name}",
        metadata={
            "source": "raw_corpus",
            "config": str(config_path),
            "corpus_ids": [corpus.id for corpus in config.corpora],
            "resolver_profile_ids": requested_resolver_profile_ids,
            "provider_settings": provider_settings,
        },
    )
    store.update_job_status(job_id, "indexing", f"Indexing {config.name}")

    document_count = 0
    chunk_count = 0
    evidence_count = 0
    edge_count = 0

    try:
        resolver_profiles = _resolver_profiles_from_store(store, requested_resolver_profile_ids)
        active_resolver_profile_ids = [profile.id for profile in resolver_profiles]
        store.update_job_status(
            job_id,
            "indexing",
            f"Indexing {config.name}",
            metadata={"resolver_profile_ids": active_resolver_profile_ids},
        )
        actual_source_roots = {
            corpus.id: resolve_corpus_root(corpus, config_path, source_roots or {})
            for corpus in config.corpora
        }
        for corpus in config.corpora:
            source_root = actual_source_roots[corpus.id]
            missing_folder = next(
                (folder for folder in _configured_corpus_scan_folders(corpus, source_root) if not folder.scan_root.exists()),
                None,
            )
            if missing_folder is not None:
                error_message = f"source root not found: {missing_folder.scan_root}"
                store.upsert_corpus(
                    corpus_id=corpus.id,
                    repo=corpus.repo,
                    source_root=str(source_root),
                    include=corpus.include,
                    status="failed",
                    file_count=0,
                    metadata={
                        "relative_root": corpus.relative_root,
                        "scan_roots": _scan_folder_metadata(_configured_corpus_scan_folders(corpus, source_root)),
                        "subfolders": _full_corpus_subfolder_metadata(corpus),
                        "error": error_message,
                    },
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
                metadata={
                    "relative_root": corpus.relative_root,
                    "scan_root": str(corpus_summary["scan_root"]),
                    "scan_roots": corpus_summary.get("scan_roots", []),
                    "subfolders": _full_corpus_subfolder_metadata(corpus),
                },
            )

        for query in scan["queries"]:
            corpus_id = str(query["corpus"])
            corpus = next(item for item in config.corpora if item.id == corpus_id)
            corpus_resolver_profiles = _resolver_profiles_for_corpus(resolver_profiles, corpus.id, corpus.repo)
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
                evidence_count += _index_chunk_evidence(store, indexed, [query_config], corpus_resolver_profiles)
                edge_count += _index_chunk_edges(store, indexed, [query_config])

        indexed_paths = set(document_ids.keys())
        for corpus in config.corpora:
            source_root = actual_source_roots[corpus.id]
            corpus_resolver_profiles = _resolver_profiles_for_corpus(resolver_profiles, corpus.id, corpus.repo)
            code_files: List[Path] = []
            for file_path in _iter_corpus_source_files(_configured_corpus_scan_folders(corpus, source_root)):
                display_path = _display_source_path(file_path, source_root, source_root)
                key = (corpus.id, display_path)
                source_type = _source_type_for_path(file_path)
                if source_type == "code":
                    code_files.append(file_path)
                    continue
                if key in indexed_paths:
                    continue
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
                    evidence_count += _index_chunk_evidence(store, indexed, [], corpus_resolver_profiles)
                    edge_count += _index_chunk_edges(store, indexed, [])
            edge_count += _index_deterministic_code_graph_files(
                store,
                code_files,
                source_root,
                corpus_resolver_profiles,
                corpus_id=corpus.id,
                repo=corpus.repo,
            )

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
                metadata={
                    "relative_root": corpus.relative_root,
                    "scan_root": str(corpus_summary["scan_root"]),
                    "scan_roots": corpus_summary.get("scan_roots", []),
                    "subfolders": _full_corpus_subfolder_metadata(corpus),
                },
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
        "job_status": "succeeded",
        "resolver_profile_ids": active_resolver_profile_ids,
        "provider_settings": provider_settings,
    }


def query_evidence(
    db_path: Path,
    query: str,
    limit: Optional[int] = None,
    ip_block: str = "",
    asic_or_generation: str = "",
    source_types: Optional[Iterable[str]] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
    function_view: str = "concept",
    compact_graph: bool = False,
) -> Dict[str, Any]:
    function_view = _normalize_function_view(function_view)
    limits = load_workbench_limits()
    result_limit = limit if limit is not None else limits.int_value("retrieval", "result_limit", minimum=1)
    if result_limit is None:
        raise ValueError(f"retrieval.resultLimit is missing from {limits.path}")
    candidate_multiplier = limits.int_value("retrieval", "candidate_multiplier", minimum=1)
    candidate_floor = limits.int_value("retrieval", "candidate_floor", minimum=1)
    max_query_tokens = limits.int_value("retrieval", "max_query_tokens", minimum=1)
    vector_limit = limits.int_value("retrieval", "vector_limit", minimum=1)
    if candidate_multiplier is None or candidate_floor is None or max_query_tokens is None or vector_limit is None:
        raise ValueError(f"retrieval candidate limits are missing from {limits.path}")
    source_type_filter = {
        source_type.strip().lower()
        for source_type in (source_types or [])
        if source_type and source_type.strip()
    }
    if not _sqlite_table_exists(db_path, "evidence"):
        return {
            "query": query,
            "queryId": "",
            "db_path": str(db_path),
            "rows": [],
            "graph": {"queryId": "", "nodes": [], "edges": [], "source": "sqlite"},
            "empty": True,
            "empty_state": f"No evidence matched query: {query}",
            "filters": {
                "ip_block": ip_block,
                "asic_or_generation": asic_or_generation,
                "source_types": sorted(source_type_filter),
            },
            "source": "sqlite",
        }
    store = AsipStore.connect(str(db_path))
    tokens = _query_tokens(query)
    symbol_prefixes = _query_symbol_prefixes(query)
    for prefix in symbol_prefixes:
        token = prefix.rstrip("_")
        if len(token) > 2 and token not in tokens:
            tokens.insert(0, token)
    access_intents = _query_access_intents(query)
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
    vector_chunk_runtimes: Dict[int, str] = {}
    vector_chunk_providers: Dict[int, str] = {}
    vector_chunk_models: Dict[int, str] = {}
    vector_chunk_embedding_sources: Dict[int, str] = {}
    query_vector: Dict[str, Any] = {"source": "not-run"}
    if symbol_prefixes:
        query_vector = {"source": "skipped-symbol-prefix"}
    elif any(_query_token_looks_like_symbol(token) for token in tokens):
        query_vector = {"source": "skipped-symbol-token"}
    elif query.strip():
        query_vector = _query_vector_for_retrieval(db_path, query, embedding_transport=embedding_transport)
        vector_kwargs = {}
        if query_vector.get("source") == "provider":
            vector_kwargs = {
                "provider": str(query_vector["provider"]),
                "model": str(query_vector["model"]),
            }
        try:
            for match in store.search_vector(
                query_vector["vector"],
                limit=vector_limit,
                **vector_kwargs,
            ):
                metadata = _embedding_metadata_from_vector_match(match)
                if not _vector_match_compatible_with_query(query_vector, metadata):
                    continue
                vector_score = float(match.get("score") or 0)
                if vector_score >= 0.75:
                    chunk_id = int(match["chunk_id"])
                    vector_chunk_scores[chunk_id] = vector_score
                    vector_chunk_runtimes[chunk_id] = str(match.get("retrieval_runtime") or "unknown")
                    vector_chunk_providers[chunk_id] = str(match.get("provider") or "")
                    vector_chunk_models[chunk_id] = str(match.get("model") or "")
                    vector_chunk_embedding_sources[chunk_id] = str(metadata.get("source") or "")
        except Exception:
            vector_chunk_scores = {}
            vector_chunk_runtimes = {}
            vector_chunk_providers = {}
            vector_chunk_models = {}
            vector_chunk_embedding_sources = {}

    vector_chunk_ids = list(vector_chunk_scores)
    candidate_chunk_ids = [
        *vector_chunk_ids,
        *[chunk_id for chunk_id in fts_chunk_ids if chunk_id not in vector_chunk_scores],
    ]
    candidates = (
        store.find_evidence_candidates(
            tokens,
            candidate_chunk_ids,
            limit=max(result_limit * candidate_multiplier, candidate_floor),
            max_query_tokens=max_query_tokens,
        )
        if tokens
        else store.all_evidence()
    )
    if vector_chunk_ids:
        existing_candidate_ids = {
            int(row["id"])
            for row in candidates
            if row.get("id") not in (None, "")
        }
        for row in store.evidence_for_chunks(vector_chunk_ids):
            row_id = int(row["id"])
            if row_id in existing_candidate_ids:
                continue
            candidates.append(row)
            existing_candidate_ids.add(row_id)
    rows: List[Dict[str, Any]] = []
    for row in candidates:
        if not is_graph_entity_endpoint(str(row.get("symbol") or "")):
            continue
        if symbol_prefixes and not _row_matches_query_symbol_prefixes(row, symbol_prefixes):
            continue
        if ip_filter and str(row.get("ip_block") or "").lower() != ip_filter:
            continue
        if asic_filter and str(row.get("asic_or_generation") or "").lower() != asic_filter:
            continue
        if source_type_filter and str(row.get("source_type") or "").lower() not in source_type_filter:
            continue
        score = _evidence_score(row, tokens, fts_chunk_ids, access_intents)
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
            if (
                query_vector.get("source") == "provider"
                and vector_chunk_embedding_sources.get(chunk_id) == "provider"
                and vector_chunk_providers.get(chunk_id)
            ):
                retrieval_sources.append("provider-vector")
            else:
                retrieval_sources.append("vector")
            result["vector_score"] = round(vector_score, 4)
            result["vector_runtime"] = vector_chunk_runtimes.get(chunk_id, "unknown")
            result["query_embedding_source"] = query_vector.get("source", "unknown")
            if query_vector.get("error"):
                result["query_embedding_error"] = query_vector["error"]
            if vector_chunk_providers.get(chunk_id):
                result["vector_provider"] = vector_chunk_providers[chunk_id]
            if vector_chunk_models.get(chunk_id):
                result["vector_model"] = vector_chunk_models[chunk_id]
            if vector_chunk_embedding_sources.get(chunk_id):
                result["vector_embedding_source"] = vector_chunk_embedding_sources[chunk_id]
        result["retrieval_sources"] = retrieval_sources
        rows.append(result)

    rows.sort(key=lambda item: (-float(item["rank_score"]), str(item["symbol"]), int(item["id"])))
    rows = _select_diverse_rows(_dedupe_rows(rows), result_limit)
    if rows:
        graph = graph_for_rows(rows, db_path, function_view=function_view, compact=compact_graph)
        rows = _merge_access_intent_edge_rows(rows, graph, symbol_prefixes, access_intents, result_limit)
    else:
        graph_seed = query.strip()
        graph = (
            expand_query_graph(db_path, graph_seed, function_view=function_view, compact=compact_graph)
            if graph_seed and is_graph_entity_endpoint(graph_seed) and _sqlite_table_exists(db_path, "edges")
            else graph_for_rows(rows, db_path, function_view=function_view)
        )
    return {
        "query": query,
        "queryId": _query_id_for_results(query, rows),
        "db_path": str(db_path),
        "rows": rows,
        "graph": graph,
        "empty": not rows,
        "empty_state": f"No evidence matched query: {query}" if not rows else "",
        "filters": {
            "ip_block": ip_block,
            "asic_or_generation": asic_or_generation,
            "source_types": sorted(source_type_filter),
        },
        "query_embedding": {
            key: value for key, value in query_vector.items() if key != "vector"
        },
        "source": "sqlite",
    }


def _merge_access_intent_edge_rows(
    rows: List[Dict[str, Any]],
    graph: Mapping[str, Any],
    symbol_prefixes: List[str],
    access_intents: set[str],
    limit: int,
) -> List[Dict[str, Any]]:
    if not rows or not symbol_prefixes or not access_intents or limit <= 0:
        return rows
    edge_rows: List[Dict[str, Any]] = []
    for edge in graph.get("edges", []):
        relation = str(edge.get("relation") or "")
        if not _access_type_matches_intents(relation, access_intents):
            continue
        src = str(edge.get("src") or "")
        dst = str(edge.get("dst") or "")
        src_label = _graph_endpoint_label(src)
        dst_label = _graph_endpoint_label(dst)
        target_symbol = ""
        function_symbol = ""
        if _symbol_matches_query_prefixes(dst_label, symbol_prefixes):
            target_symbol = dst_label
            function_symbol = src_label
        elif _symbol_matches_query_prefixes(src_label, symbol_prefixes):
            target_symbol = src_label
            function_symbol = dst_label
        if not target_symbol or not function_symbol:
            continue
        source = _first_edge_source(edge)
        confidence = float(edge.get("confidence") or edge.get("weight") or 0)
        path = str(source.get("path") or "")
        line_start = source.get("line_start")
        line_end = source.get("line_end") or line_start
        edge_rows.append(
            {
                "id": f"graph-edge:{src}:{relation}:{dst}:{path}:{line_start or ''}",
                "chunk_id": 0,
                "corpus_id": str(source.get("corpus_id") or ""),
                "source_type": "code",
                "repo": str(source.get("repo") or ""),
                "path": path,
                "line_start": line_start,
                "line_end": line_end,
                "symbol": function_symbol,
                "target_symbol": target_symbol,
                "entity_type": "function",
                "access_type": relation,
                "confidence": confidence,
                "snippet": f"{function_symbol} {relation} {target_symbol}",
                "resolved_chain": f"{function_symbol} {relation} {target_symbol}",
                "query_id": "",
                "rank_score": round(100 + confidence, 4),
                "tone": "code",
                "source": "code",
                "score": f"{confidence:.2f}",
                "relation": relation,
                "retrieval_sources": ["graph-edge"],
                "stage": str(edge.get("stage") or ""),
                "edge_source": str(edge.get("source") or ""),
            }
        )
    if not edge_rows:
        return rows
    merged: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, object]] = set()
    for row in [*edge_rows, *rows]:
        key = (
            str(row.get("symbol") or ""),
            str(row.get("relation") or row.get("access_type") or ""),
            str(row.get("target_symbol") or ""),
            str(row.get("path") or ""),
            row.get("line_start") or row.get("page") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged


def _symbol_matches_query_prefixes(symbol: str, symbol_prefixes: List[str]) -> bool:
    variants = [symbol, _canonical_graph_seed_symbol(symbol)]
    return any(
        variant.lower().startswith(prefix)
        for variant in variants
        for prefix in symbol_prefixes
    )


def _graph_endpoint_label(endpoint: str) -> str:
    return endpoint.rsplit(":", 1)[-1] if ":" in endpoint else endpoint


def _first_edge_source(edge: Mapping[str, Any]) -> Dict[str, Any]:
    attr = edge.get("attr")
    if isinstance(attr, Mapping):
        for key in ("source", "implementations"):
            values = attr.get(key)
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, Mapping):
                        return dict(value)
            if isinstance(values, Mapping):
                return dict(values)
    return {}


def _query_id_for_results(query: str, rows: Iterable[Mapping[str, Any]]) -> str:
    row_list = list(rows)
    explicit = next((str(row.get("query_id") or "") for row in row_list if row.get("query_id")), "")
    if explicit:
        return explicit
    if not row_list:
        return ""
    corpus_id = str(row_list[0].get("corpus_id") or "query").strip() or "query"
    query_slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")
    return f"{corpus_id}_{query_slug}" if query_slug else corpus_id


def _query_vector_for_retrieval(
    db_path: Path,
    query: str,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    provider_settings = load_provider_settings(db_path)
    config = _embedding_provider_config(provider_settings)
    if config is not None:
        try:
            provider = create_embedding_provider(config)
            if embedding_transport is not None and hasattr(provider, "transport"):
                provider.transport = embedding_transport
            vector = provider.embed([query], config)[0]
            return {
                "vector": vector,
                "source": "provider",
                "provider": config.provider,
                "model": config.model,
            }
        except Exception as exc:
            return {
                "vector": _deterministic_embedding(query),
                "source": "deterministic-fallback",
                "error": str(exc),
            }
    return {"vector": _deterministic_embedding(query), "source": "deterministic"}


def _embedding_metadata_from_vector_match(match: Mapping[str, Any]) -> Dict[str, Any]:
    raw = match.get("metadata_json")
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _json_object(raw: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _vector_match_compatible_with_query(
    query_vector: Mapping[str, Any],
    embedding_metadata: Mapping[str, Any],
) -> bool:
    query_source = str(query_vector.get("source") or "")
    embedding_source = str(embedding_metadata.get("source") or "")
    if query_source == "deterministic-fallback":
        return embedding_source in {"deterministic", "deterministic-fallback"}
    return True


def get_evidence_detail(db_path: Path, evidence_id: int) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "evidence"):
        raise ValueError(f"evidence id not found: {evidence_id}")
    store = AsipStore.connect(str(db_path))
    for row in store.all_evidence():
        if int(row["id"]) == int(evidence_id):
            detail = _json_ready(row)
            detail["resolved_chain_explanation"] = _resolved_chain_explanation_for_row(detail)
            return detail
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
        "resolved_chain_explanations": [
            _resolved_chain_explanation_for_row(row)
            for row in evidence.get("rows", [])
            if row.get("resolved_chain")
        ],
    }


def expand_query_graph(
    db_path: Path,
    symbol: str,
    hops: int = 1,
    function_view: str = "concept",
    compact: bool = False,
) -> Dict[str, Any]:
    function_view = _normalize_function_view(function_view)
    if not is_graph_entity_endpoint(symbol):
        return {
            "queryId": symbol,
            "nodes": [],
            "edges": [],
            "source": "networkx",
            "graph_runtime": "networkx",
            "empty_state": f"{symbol} is a resolver operator, not a graph entity",
        }
    graph_seed = _canonical_graph_seed_symbol(symbol)
    if not _sqlite_table_exists(db_path, "edges"):
        fallback_node = _product_fallback_node(symbol)
        if fallback_node is None:
            return {
                "queryId": symbol,
                "nodes": [],
                "edges": [],
                "source": "networkx",
                "graph_runtime": "networkx",
                "empty_state": f"{symbol} is not a product graph entity",
            }
        return {
            "queryId": symbol,
            "nodes": [fallback_node],
            "edges": [],
            "source": "networkx",
            "graph_runtime": "networkx",
        }
    store = AsipStore.connect(str(db_path))
    graph = store.expand_graph_networkx(graph_seed, hops=hops, function_view=function_view)
    return {
        "queryId": symbol,
        "nodes": [_graph_node_payload(node, compact=compact) for node in graph["nodes"]],
        "edges": [_graph_edge_payload(edge, compact=compact) for edge in graph["edges"]],
        "source": "networkx",
        "graph_runtime": graph["graph_runtime"],
        "metadata_mode": "compact" if compact else "full",
    }


def _canonical_graph_seed_symbol(symbol: str) -> str:
    cleaned = symbol.strip()
    for prefix in ("reg", "mm", "smn"):
        if cleaned.startswith(prefix) and len(cleaned) > len(prefix) and cleaned[len(prefix)].isupper():
            return cleaned[len(prefix) :]
    return cleaned


def global_graph(
    db_path: Path,
    limit: Optional[int] = None,
    include_evidence_derived: bool = False,
    evidence_row_cap: Optional[int] = None,
    all_edges: bool = False,
    function_view: str = "concept",
    compact: bool = False,
) -> Dict[str, Any]:
    function_view = _normalize_function_view(function_view)
    limits = load_workbench_limits()
    edge_limit = None if all_edges else (limit if limit is not None else limits.int_value("graph", "edge_budget", minimum=1))
    effective_evidence_cap = (
        evidence_row_cap
        if evidence_row_cap is not None
        else limits.int_value("graph", "evidence_row_cap", minimum=0)
    )
    cooccurrence_limit = limits.int_value("graph", "cooccurrence_symbol_limit", minimum=0)
    if not _sqlite_table_exists(db_path, "edges"):
        return {
            "queryId": "global",
            "nodes": [],
            "edges": [],
            "source": "networkx",
            "graph_runtime": "networkx",
        }
    store = AsipStore.connect(str(db_path))
    graph = store.global_graph_networkx(
        limit=edge_limit,
        include_evidence_derived=include_evidence_derived,
        evidence_row_cap=effective_evidence_cap,
        cooccurrence_symbol_limit=cooccurrence_limit,
        function_view=function_view,
        compact=compact,
    )
    return {
        "queryId": "global",
        "nodes": [_graph_node_payload(node, compact=compact) for node in graph["nodes"]],
        "edges": [_graph_edge_payload(edge, compact=compact) for edge in graph["edges"]],
        "source": "networkx",
        "graph_runtime": graph["graph_runtime"],
        "metadata_mode": "compact" if compact else "full",
    }


def graph_for_rows(
    rows: List[Dict[str, Any]],
    db_path: Path,
    function_view: str = "concept",
    compact: bool = False,
) -> Dict[str, Any]:
    function_view = _normalize_function_view(function_view)
    if not rows:
        return {"queryId": "", "nodes": [], "edges": [], "source": "sqlite"}
    limits = load_workbench_limits()
    query_seed_limit = limits.int_value("graph", "query_seed_limit", minimum=1)
    if query_seed_limit is None:
        raise ValueError(f"graph.querySeedLimit is missing from {limits.path}")
    query_hops = limits.int_value("graph", "default_hops", minimum=1)
    if query_hops is None:
        raise ValueError(f"graph.defaultHops is missing from {limits.path}")
    node_by_id: Dict[str, Dict[str, Any]] = {}
    edge_by_key: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    seeds: List[str] = []
    for row in rows:
        symbol = str(row["symbol"])
        if symbol in seeds:
            continue
        seeds.append(symbol)
        if len(seeds) >= query_seed_limit:
            break
    if not _sqlite_table_exists(db_path, "edges"):
        return expand_query_graph(db_path, str(rows[0]["symbol"]), hops=query_hops, function_view=function_view)
    store = AsipStore.connect(str(db_path))
    graph = store.expand_graph_networkx_many(
        [_canonical_graph_seed_symbol(seed) for seed in seeds],
        hops=query_hops,
        function_view=function_view,
    )
    for node in graph["nodes"]:
        _remember_graph_node_payload(node_by_id, node, compact=compact)
    for edge in graph["edges"]:
        ready_edge = _graph_edge_payload(edge, compact=compact)
        key = (str(ready_edge["src"]), str(ready_edge["relation"]), str(ready_edge["dst"]))
        edge_by_key.setdefault(key, ready_edge)
    section_graph = section_overlay_graph_for_evidence_rows(rows)
    for node in section_graph["nodes"]:
        _remember_graph_node_payload(node_by_id, node, compact=compact)
    for edge in section_graph["edges"]:
        ready_edge = _graph_edge_payload(edge, compact=compact)
        key = (str(ready_edge["src"]), str(ready_edge["relation"]), str(ready_edge["dst"]))
        edge_by_key.setdefault(key, ready_edge)
    if not edge_by_key:
        return {
            "queryId": ", ".join(seeds),
            "nodes": sorted(node_by_id.values(), key=lambda node: str(node["id"])),
            "edges": [],
            "source": "networkx",
            "graph_runtime": graph["graph_runtime"],
            "metadata_mode": "compact" if compact else "full",
        }
    return {
        "queryId": ", ".join(seeds),
        "nodes": sorted(node_by_id.values(), key=lambda node: str(node["id"])),
        "edges": sorted(
            edge_by_key.values(),
            key=lambda edge: (-float(edge.get("weight") or edge.get("confidence") or 0), str(edge["src"]), str(edge["dst"])),
        ),
        "source": "networkx",
        "graph_runtime": "networkx",
        "metadata_mode": "compact" if compact else "full",
    }


def _normalize_function_view(function_view: str) -> str:
    view = str(function_view or "concept").strip().lower()
    if view not in {"concept", "implementation"}:
        raise ValueError("function_view must be concept or implementation")
    return view


def _remember_graph_node_payload(
    node_by_id: Dict[str, Dict[str, Any]],
    node: Mapping[str, Any],
    compact: bool = False,
) -> None:
    node_id = str(node["id"])
    payload = _graph_node_payload(node, compact=compact)
    existing = node_by_id.get(node_id)
    if existing is None:
        node_by_id[node_id] = payload
        return
    _merge_graph_node_payload(existing, payload)


def _merge_graph_node_payload(existing: Dict[str, Any], incoming: Mapping[str, Any]) -> None:
    for key in ("kind", "label"):
        if not existing.get(key) and incoming.get(key):
            existing[key] = incoming[key]
    existing["weight"] = max(float(existing.get("weight") or 0), float(incoming.get("weight") or 0), 1.0)
    for key in ("in", "out"):
        existing[key] = _dedupe_graph_string_values(
            [
                *_list_graph_values(existing.get(key)),
                *_list_graph_values(incoming.get(key)),
            ]
        )
    existing_attr = existing.setdefault("attr", {})
    if not isinstance(existing_attr, dict):
        existing_attr = {}
        existing["attr"] = existing_attr
    incoming_attr = incoming.get("attr")
    if isinstance(incoming_attr, Mapping):
        _merge_graph_attr(existing_attr, incoming_attr)


def _merge_graph_attr(existing: Dict[str, Any], incoming: Mapping[str, Any]) -> None:
    for key, value in incoming.items():
        if value in ("", None, 0):
            continue
        if key == "source":
            existing[key] = _dedupe_graph_source_records(
                [*_list_graph_values(existing.get(key)), *_list_graph_values(value)]
            )
            continue
        if isinstance(value, list):
            existing[key] = _dedupe_graph_string_values(
                [*_list_graph_values(existing.get(key)), *_list_graph_values(value)]
            )
            continue
        current = existing.get(key)
        if current in ("", None, 0, "unknown"):
            existing[key] = value


def _dedupe_graph_source_records(values: Iterable[Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for value in values:
        if not isinstance(value, Mapping):
            continue
        record = {str(key): item for key, item in value.items() if item not in ("", None, 0)}
        if not record:
            continue
        marker = tuple(sorted((str(key), str(item)) for key, item in record.items()))
        if marker in seen:
            continue
        seen.add(marker)
        records.append(record)
    concrete = [record for record in records if not _is_unknown_graph_source_record(record)]
    return concrete or records


def _is_unknown_graph_source_record(record: Mapping[str, Any]) -> bool:
    return (
        str(record.get("corpus_id") or "unknown") == "unknown"
        and str(record.get("repo") or "unknown") == "unknown"
        and str(record.get("path") or "") == ""
    )


def _list_graph_values(value: Any) -> List[Any]:
    if value in ("", None, 0):
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dedupe_graph_string_values(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        if value in ("", None, 0):
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _configured_corpus_scan_folders(corpus: FullCorpus, source_root: Path) -> List[CorpusScanFolder]:
    return [
        CorpusScanFolder(
            relative_root=normalize_corpus_relative_root(folder.relative_root),
            include=[str(item) for item in (folder.include or corpus.include or ["**/*.c", "**/*.h"])],
            scan_root=_corpus_scan_root(source_root, folder.relative_root),
        )
        for folder in full_corpus_scan_folders(corpus)
    ]


def _registered_corpus_scan_folders(corpus: Mapping[str, Any], source_root: Path) -> List[CorpusScanFolder]:
    include = [str(item) for item in corpus.get("include", [])] or ["**/*"]
    metadata = dict(corpus.get("metadata", {})) if isinstance(corpus.get("metadata"), Mapping) else {}
    raw_subfolders = metadata.get("subfolders", [])
    folders = _normalize_subfolder_filters(raw_subfolders, default_include=include)
    if not folders:
        relative_root = str(metadata.get("relative_root") or "")
        folders = [{"relative_root": relative_root, "include": include}]
    return [
        CorpusScanFolder(
            relative_root=normalize_corpus_relative_root(folder.get("relative_root") or ""),
            include=[str(item) for item in folder.get("include", include)] or include,
            scan_root=_corpus_scan_root(source_root, folder.get("relative_root") or ""),
        )
        for folder in folders
    ]


def _corpus_scan_root(source_root: Path, relative_root: Any) -> Path:
    normalized = normalize_corpus_relative_root(relative_root)
    scan_root = source_root / normalized if normalized else source_root
    resolved_source_root = source_root.resolve(strict=False)
    resolved_scan_root = scan_root.resolve(strict=False)
    if resolved_scan_root != resolved_source_root and resolved_source_root not in resolved_scan_root.parents:
        raise ValueError(f"corpus subfolder must be repo-relative: {relative_root}")
    return scan_root


def _iter_corpus_source_files(folders: Iterable[CorpusScanFolder]) -> List[Path]:
    files: List[Path] = []
    seen: set[Path] = set()
    for folder in folders:
        for file_path in _iter_source_files(folder.scan_root, folder.include):
            file_key = file_path.resolve(strict=False)
            if file_key in seen:
                continue
            seen.add(file_key)
            files.append(file_path)
    return sorted(files)


def _scan_folder_metadata(folders: Iterable[CorpusScanFolder]) -> List[Dict[str, Any]]:
    return [
        {
            "relative_root": folder.relative_root,
            "scan_root": str(folder.scan_root),
            "include": list(folder.include),
        }
        for folder in folders
    ]


def _scan_folder_metadata_with_counts(folders: Iterable[CorpusScanFolder]) -> List[Dict[str, Any]]:
    metadata = []
    for folder in folders:
        files = list(_iter_source_files(folder.scan_root, folder.include))
        metadata.append(
            {
                "relative_root": folder.relative_root,
                "scan_root": str(folder.scan_root),
                "include": list(folder.include),
                "file_count": len(files),
            }
        )
    return metadata


def _full_corpus_subfolder_metadata(corpus: FullCorpus) -> List[Dict[str, Any]]:
    if not corpus.subfolders:
        return []
    return [
        {"relative_root": str(folder.relative_root or ""), "include": [str(item) for item in folder.include]}
        for folder in corpus.subfolders
    ]


def _normalize_subfolder_filters(raw_subfolders: Any, default_include: Iterable[str]) -> List[Dict[str, Any]]:
    default_include_list = [str(item) for item in default_include] or ["**/*"]
    if raw_subfolders in ("", None):
        return []
    if isinstance(raw_subfolders, str):
        raw_items: Iterable[Any] = [item.strip() for item in raw_subfolders.splitlines() if item.strip()]
    elif isinstance(raw_subfolders, list):
        raw_items = raw_subfolders
    else:
        return []
    folders: List[Dict[str, Any]] = []
    for raw in raw_items:
        if isinstance(raw, str):
            relative_root, _, include_text = raw.partition(":")
            if not include_text and "=" in relative_root:
                relative_root, _, include_text = relative_root.partition("=")
            include = [item.strip() for item in include_text.split(",") if item.strip()] if include_text else default_include_list
            folders.append({"relative_root": normalize_corpus_relative_root(relative_root, allow_empty=False), "include": include})
            continue
        if not isinstance(raw, Mapping):
            continue
        relative_root = normalize_corpus_relative_root(
            raw.get("relative_root", raw.get("relativeRoot", raw.get("root", raw.get("path", "")))),
            allow_empty=False,
        )
        include_raw = raw.get("include", default_include_list)
        if isinstance(include_raw, str):
            include = [item.strip() for item in include_raw.split(",") if item.strip()]
        elif isinstance(include_raw, list):
            include = [str(item).strip() for item in include_raw if str(item).strip()]
        else:
            include = default_include_list
        folders.append({"relative_root": relative_root, "include": include or default_include_list})
    return folders


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
                "metadata": {
                    "relative_root": corpus.relative_root,
                    "subfolders": _full_corpus_subfolder_metadata(corpus),
                },
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
            "metadata": {
                "relative_root": corpus.relative_root,
                "subfolders": _full_corpus_subfolder_metadata(corpus),
            },
        }
        for corpus in config.corpora
    ]


def list_jobs(db_path: Path, limit: int = 50) -> List[Dict[str, Any]]:
    if not _sqlite_table_exists(db_path, "jobs"):
        return []
    store = AsipStore.connect(str(db_path))
    return store.list_jobs(limit=limit)


def get_job(db_path: Path, job_id: int) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "jobs"):
        raise KeyError(job_id)
    store = AsipStore.connect(str(db_path))
    return store.get_job(job_id)


def supersede_stale_jobs(
    db_path: Path,
    *,
    before_job_id: int,
    kind: str = "index",
    message: Optional[str] = None,
) -> Dict[str, Any]:
    if not _sqlite_table_exists(db_path, "jobs"):
        return {
            "source": "job_hygiene",
            "db_path": str(db_path),
            "kind": kind,
            "before_job_id": before_job_id,
            "superseded_job_ids": [],
        }
    store = AsipStore.connect(str(db_path))
    stale_rows = store.con.execute(
        """
        select id
        from jobs
        where kind = ?
          and id < ?
          and status in ('queued', 'indexing', 'failed')
        order by id
        """,
        (kind, before_job_id),
    ).fetchall()
    stale_ids = [int(row["id"]) for row in stale_rows]
    supersede_message = message or f"Superseded by job {before_job_id}"
    for job_id in stale_ids:
        store.finish_job(job_id, "superseded", supersede_message)
    return {
        "source": "job_hygiene",
        "db_path": str(db_path),
        "kind": kind,
        "before_job_id": before_job_id,
        "superseded_job_ids": stale_ids,
    }


def add_corpus(
    db_path: Path,
    corpus_id: str,
    repo: str,
    source_root: str,
    include: Iterable[str],
    corpus_type: str = "code",
    subfolders: Any = None,
) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    include_list = [str(item) for item in include]
    subfolder_filters = _normalize_subfolder_filters(subfolders, default_include=include_list)
    metadata: Dict[str, Any] = {"type": corpus_type}
    if subfolder_filters:
        metadata["subfolders"] = subfolder_filters
    store.upsert_corpus(
        corpus_id=corpus_id,
        repo=repo,
        source_root=source_root,
        include=include_list,
        status="not_indexed",
        file_count=0,
        metadata=metadata,
    )
    return {
        "id": corpus_id,
        "repo": repo,
        "source_root": source_root,
        "include": include_list,
        "status": "not_indexed",
        "file_count": 0,
        "metadata": metadata,
    }


def index_registered_corpora(
    db_path: Path,
    corpus_ids: Optional[Iterable[str]] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
    resolver_profile_ids: Optional[Iterable[str]] = None,
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
    requested_resolver_profile_ids = _normal_resolver_profile_ids(resolver_profile_ids)
    job_id = store.start_job(
        "index",
        f"Indexing registered corpora: {', '.join(selected_ids)}",
        metadata={
            "source": "registered_corpus",
            "corpus_ids": selected_ids,
            "resolver_profile_ids": requested_resolver_profile_ids,
            "provider_settings": provider_settings,
        },
    )
    store.update_job_status(job_id, "indexing", f"Indexing registered corpora: {', '.join(selected_ids)}")

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
        resolver_profiles = _resolver_profiles_from_store(store, requested_resolver_profile_ids)
        active_resolver_profile_ids = [profile.id for profile in resolver_profiles]
        store.update_job_status(
            job_id,
            "indexing",
            f"Indexing registered corpora: {', '.join(selected_ids)}",
            metadata={"resolver_profile_ids": active_resolver_profile_ids},
        )
        for corpus in selected:
            corpus_id = str(corpus["id"])
            source_root = Path(str(corpus["source_root"])).expanduser()
            include = [str(item) for item in corpus["include"]]
            corpus_resolver_profiles = _resolver_profiles_for_corpus(
                resolver_profiles,
                corpus_id,
                str(corpus["repo"]),
            )
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
            scan_folders = _registered_corpus_scan_folders(corpus, source_root)
            missing_folder = next((folder for folder in scan_folders if not folder.scan_root.exists()), None)
            if missing_folder is not None:
                error_message = f"source root not found: {missing_folder.scan_root}"
                store.upsert_corpus(
                    corpus_id=corpus_id,
                    repo=str(corpus["repo"]),
                    source_root=str(source_root),
                    include=include,
                    status="failed",
                    file_count=0,
                    metadata={**dict(corpus.get("metadata", {})), "scan_roots": _scan_folder_metadata(scan_folders), "error": error_message},
                )
                raise FileNotFoundError(error_message)
            files = _iter_corpus_source_files(scan_folders)
            file_count += len(files)
            code_files: List[Path] = []
            store.upsert_corpus(
                corpus_id=corpus_id,
                repo=str(corpus["repo"]),
                source_root=str(source_root),
                include=include,
                status="indexing",
                file_count=len(files),
                metadata={**dict(corpus.get("metadata", {})), "scan_roots": _scan_folder_metadata_with_counts(scan_folders)},
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
                    evidence_count += _index_chunk_evidence(store, indexed, [], corpus_resolver_profiles)
                    edge_count += _index_chunk_edges(store, indexed, [])
                if source_type == "code":
                    code_files.append(file_path)
            edge_count += _index_deterministic_code_graph_files(
                store,
                code_files,
                source_root,
                corpus_resolver_profiles,
                corpus_id=corpus_id,
                repo=str(corpus["repo"]),
            )
            store.upsert_corpus(
                corpus_id=corpus_id,
                repo=str(corpus["repo"]),
                source_root=str(source_root),
                include=include,
                status="indexed",
                file_count=len(files),
                metadata={**dict(corpus.get("metadata", {})), "scan_roots": _scan_folder_metadata_with_counts(scan_folders)},
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
        "job_status": "succeeded",
        "resolver_profile_ids": active_resolver_profile_ids,
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


def rebuild_deterministic_graph(
    db_path: Path,
    corpus_ids: Optional[Iterable[str]] = None,
    resolver_profile_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Rebuild Stage 1 deterministic graph edges from registered corpus source roots."""

    if not _sqlite_table_exists(db_path, "corpora"):
        raise ValueError("no registered corpora found")
    store = AsipStore.connect(str(db_path))
    store.migrate()
    corpora = store.list_corpora()
    selected_ids = list(corpus_ids or [str(corpus["id"]) for corpus in corpora if str(corpus.get("status") or "") == "indexed"])
    known_ids = {str(corpus["id"]) for corpus in corpora}
    unknown_ids = [corpus_id for corpus_id in selected_ids if corpus_id not in known_ids]
    if unknown_ids:
        raise ValueError(f"unknown corpus id(s): {', '.join(unknown_ids)}")
    selected = [corpus for corpus in corpora if str(corpus["id"]) in selected_ids]
    if not selected:
        raise ValueError("no corpora selected for deterministic graph rebuild")
    requested_resolver_profile_ids = _normal_resolver_profile_ids(resolver_profile_ids)

    job_id = store.start_job(
        "graph_rebuild",
        f"Rebuilding deterministic graph for {', '.join(selected_ids)}",
        metadata={
            "corpus_ids": selected_ids,
            "resolver_profile_ids": requested_resolver_profile_ids,
            "stage": "deterministic",
        },
    )
    file_count = 0
    edge_count = 0
    try:
        if corpus_ids is None:
            store.con.execute("delete from edges where stage = 'deterministic'")
        else:
            placeholders = ", ".join("?" for _ in selected_ids)
            store.con.execute(
                f"""
                delete from edges
                where stage = 'deterministic'
                  and json_extract(provenance_json, '$.corpus_id') in ({placeholders})
                """,
                selected_ids,
            )
        store.con.commit()
        resolver_profiles = _resolver_profiles_from_store(store, requested_resolver_profile_ids)
        active_resolver_profile_ids = [profile.id for profile in resolver_profiles]
        store.update_job_status(
            job_id,
            "indexing",
            f"Rebuilding deterministic graph for {', '.join(selected_ids)}",
            metadata={"resolver_profile_ids": active_resolver_profile_ids},
        )
        for corpus in selected:
            corpus_id = str(corpus["id"])
            source_root = Path(str(corpus["source_root"])).expanduser()
            corpus_resolver_profiles = _resolver_profiles_for_corpus(
                resolver_profiles,
                corpus_id,
                str(corpus["repo"]),
            )
            if not source_root.exists():
                raise FileNotFoundError(f"source root not found: {source_root}")
            code_files: List[Path] = []
            scan_folders = _registered_corpus_scan_folders(corpus, source_root)
            missing_folder = next((folder for folder in scan_folders if not folder.scan_root.exists()), None)
            if missing_folder is not None:
                raise FileNotFoundError(f"source root not found: {missing_folder.scan_root}")
            for file_path in _iter_corpus_source_files(scan_folders):
                if _source_type_for_path(file_path) != "code":
                    continue
                file_count += 1
                code_files.append(file_path)
            edge_count += _index_deterministic_code_graph_files(
                store,
                code_files,
                source_root,
                corpus_resolver_profiles,
                corpus_id=corpus_id,
                repo=str(corpus["repo"]),
            )
        store.finish_job(job_id, "rebuilt", f"Rebuilt {edge_count} deterministic graph edges from {file_count} files")
    except Exception as exc:
        store.finish_job(job_id, "failed", str(exc))
        raise
    return {
        "source": "deterministic_graph_rebuild",
        "db_path": str(db_path),
        "corpus_ids": selected_ids,
        "files": file_count,
        "edges": edge_count,
        "job_id": job_id,
        "resolver_profile_ids": active_resolver_profile_ids,
    }


def backfill_provider_embeddings(
    db_path: Path,
    limit: Optional[int] = None,
    batch_size: Optional[int] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    """Generate provider embeddings for already indexed chunks using current settings."""

    limits = load_workbench_limits()
    effective_limit = limit if limit is not None else limits.int_value("embedding", "backfill_limit", minimum=0)
    effective_batch_size = batch_size if batch_size is not None else limits.int_value("embedding", "batch_size", minimum=1)
    max_text_chars = limits.int_value("embedding", "max_text_chars", minimum=0) or 0
    if effective_limit is None or effective_batch_size is None:
        raise ValueError(f"embedding limits are missing from {limits.path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    provider_settings = load_provider_settings(db_path)
    config = _embedding_provider_config(provider_settings)
    if config is None:
        raise ValueError("embedding provider settings are missing")
    batch_size = max(1, effective_batch_size)
    applied_limit = int(effective_limit) if effective_limit and effective_limit > 0 else None
    limit_is_unlimited = applied_limit is None
    job_id = store.start_job(
        "embedding_backfill",
        f"Backfilling provider embeddings with {config.provider}:{config.model}",
        metadata={
            "provider_settings": provider_settings,
            "limit": effective_limit,
            "requested_limit": effective_limit,
            "applied_limit": applied_limit,
            "limit_is_unlimited": limit_is_unlimited,
            "batch_size": batch_size,
        },
    )
    embedded_chunks = 0
    truncated_chunks = 0
    context_retry_chunks = 0
    provider_input_count = 0
    provider_request_count = 0
    provider_input_attempt_count = 0
    total_candidates = 0

    def progress_metadata() -> Dict[str, Any]:
        return {
            "total_candidates": total_candidates,
            "embedded_chunks": embedded_chunks,
            "provider_input_count": provider_input_count,
            "provider_request_count": provider_request_count,
            "provider_input_attempt_count": provider_input_attempt_count,
            "truncated_chunks": truncated_chunks,
            "context_retry_chunks": context_retry_chunks,
        }

    try:
        rows = _chunks_missing_provider_embedding(store, config.provider, config.model, limit=effective_limit)
        total_candidates = len(rows)
        store.update_job_status(
            job_id,
            "indexing",
            f"Embedding 0/{total_candidates} chunks with {config.provider}:{config.model}",
            metadata=progress_metadata(),
        )
        provider = create_embedding_provider(config)
        if embedding_transport is not None and hasattr(provider, "transport"):
            provider.transport = embedding_transport
        for start in range(0, len(rows), batch_size):
            row_batch = rows[start : start + batch_size]
            prepared_rows: List[Dict[str, Any]] = []
            unique_texts: List[str] = []
            seen_texts = set()
            for row in row_batch:
                prepared_text = _prepare_embedding_input_text(str(row["text"]), max_text_chars)
                text = str(prepared_text["text"])
                prepared_rows.append({"row": row, "prepared_text": prepared_text, "text": text})
                if text not in seen_texts:
                    seen_texts.add(text)
                    unique_texts.append(text)
            embedding_by_text: Dict[str, Dict[str, Any]] = {}
            attempt_stats = {"provider_request_count": 0, "provider_input_attempt_count": 0}
            try:
                batch_embeddings = _embed_provider_batch(provider, unique_texts, config, attempt_stats)
            finally:
                provider_request_count += attempt_stats["provider_request_count"]
                provider_input_attempt_count += attempt_stats["provider_input_attempt_count"]
            for text, embedding in zip(unique_texts, batch_embeddings):
                embedding_by_text[text] = embedding
            provider_input_count += len(unique_texts)
            embedding_rows: List[Dict[str, Any]] = []
            for item in prepared_rows:
                row = item["row"]
                prepared_text = item["prepared_text"]
                text = item["text"]
                embedding = embedding_by_text[text]
                metadata = {"source": "provider", **prepared_text["metadata"], **dict(embedding.get("metadata") or {})}
                if metadata.get("embedding_text_truncated"):
                    truncated_chunks += 1
                if metadata.get("embedding_context_retry"):
                    context_retry_chunks += 1
                embedding_rows.append(
                    {
                        "chunk_id": int(row["id"]),
                        "provider": config.provider,
                        "model": config.model,
                        "vector": embedding["vector"],
                        "metadata": metadata,
                    }
                )
            store.add_embeddings(embedding_rows)
            embedded_chunks += len(embedding_rows)
            store.update_job_status(
                job_id,
                "indexing",
                f"Embedded {embedded_chunks}/{total_candidates} chunks with {config.provider}:{config.model}",
                metadata=progress_metadata(),
            )
        suffix = f"; truncated {truncated_chunks} long inputs" if truncated_chunks else ""
        context_suffix = f"; context retries {context_retry_chunks}" if context_retry_chunks else ""
        dedupe_suffix = (
            f"; provider inputs {provider_input_count}/{embedded_chunks}"
            if provider_input_count != embedded_chunks
            else ""
        )
        attempt_suffix = (
            f"; provider attempts {provider_input_attempt_count} inputs/{provider_request_count} requests"
            if provider_input_attempt_count != provider_input_count or provider_request_count != provider_input_count
            else ""
        )
        store.update_job_status(job_id, "indexing", f"Finalizing {embedded_chunks}/{total_candidates} embeddings", metadata=progress_metadata())
        store.finish_job(
            job_id,
            "embedded",
            f"Embedded {embedded_chunks} chunks{suffix}{context_suffix}{dedupe_suffix}{attempt_suffix}",
        )
    except Exception as exc:
        store.update_job_status(
            job_id,
            "indexing",
            f"Failed after {embedded_chunks}/{total_candidates} embeddings",
            metadata=progress_metadata(),
        )
        store.finish_job(job_id, "failed", str(exc))
        raise
    return {
        "source": "provider_embedding_backfill",
        "db_path": str(db_path),
        "provider": config.provider,
        "model": config.model,
        "embedded_chunks": embedded_chunks,
        "provider_input_count": provider_input_count,
        "provider_request_count": provider_request_count,
        "provider_input_attempt_count": provider_input_attempt_count,
        "deduped_chunks": embedded_chunks - provider_input_count,
        "truncated_chunks": truncated_chunks,
        "context_retry_chunks": context_retry_chunks,
        "batch_size": batch_size,
        "limit": limit,
        "requested_limit": effective_limit,
        "applied_limit": applied_limit,
        "limit_is_unlimited": limit_is_unlimited,
        "job_id": job_id,
    }


def _prepare_embedding_input_text(text: str, max_text_chars: int) -> Dict[str, Any]:
    if max_text_chars <= 0 or len(text) <= max_text_chars:
        return {"text": text, "metadata": {}}
    return {
        "text": text[:max_text_chars],
        "metadata": {
            "embedding_text_truncated": True,
            "embedding_text_chars": max_text_chars,
            "original_text_chars": len(text),
        },
    }


def _embed_provider_batch(
    provider: Any,
    texts: List[str],
    config: EmbeddingProviderConfig,
    attempt_stats: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    if attempt_stats is not None:
        attempt_stats["provider_request_count"] = int(attempt_stats.get("provider_request_count", 0)) + 1
        attempt_stats["provider_input_attempt_count"] = int(attempt_stats.get("provider_input_attempt_count", 0)) + len(texts)
    try:
        return [{"vector": vector, "metadata": {}} for vector in provider.embed(texts, config)]
    except Exception as exc:
        if len(texts) > 1 and _is_provider_context_length_error(exc):
            midpoint = max(1, len(texts) // 2)
            return [
                *_embed_provider_batch(provider, texts[:midpoint], config, attempt_stats),
                *_embed_provider_batch(provider, texts[midpoint:], config, attempt_stats),
            ]
        if len(texts) == 1 and _is_provider_context_length_error(exc):
            shortened = _shorten_embedding_input_after_context_error(texts[0])
            if shortened != texts[0]:
                retry = _embed_provider_batch(provider, [shortened], config, attempt_stats)[0]
                retry_metadata = dict(retry.get("metadata") or {})
                final_text_chars = int(retry_metadata.get("embedding_text_chars") or len(shortened))
                original_text_chars = max(
                    len(texts[0]),
                    int(retry_metadata.get("original_embedding_text_chars") or 0),
                )
                retry_metadata.update(
                    {
                        "embedding_context_retry": True,
                        "embedding_text_truncated": True,
                        "embedding_text_chars": final_text_chars,
                        "original_embedding_text_chars": original_text_chars,
                    }
                )
                return [{"vector": retry["vector"], "metadata": retry_metadata}]
        raise


def _is_provider_context_length_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "context length" in message or "input length" in message or "too large" in message


def _shorten_embedding_input_after_context_error(text: str) -> str:
    if len(text) <= 1:
        return text
    return text[: max(1, len(text) // 2)]


def generate_semantic_edges_for_query(
    db_path: Path,
    query: str,
    limit: Optional[int] = None,
    edge_provider: Optional[EdgeProvider] = None,
) -> Dict[str, Any]:
    """Generate semantic edges from indexed evidence rows and persist them to the graph store."""

    limits = load_workbench_limits()
    query_limit = limit if limit is not None else limits.int_value("semantic", "query_limit", minimum=1)
    if query_limit is None:
        raise ValueError(f"semantic.queryLimit is missing from {limits.path}")
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
        evidence = query_evidence(db_path, query, limit=query_limit)
        rows = list(evidence.get("rows", []))
        if not rows:
            raise ValueError(f"no evidence rows matched query: {query}")
        prompt = _semantic_edge_prompt(query, rows)
        provider = edge_provider or create_edge_provider(config)
        generated = normalize_generated_cases(provider.generate(prompt, config))
        edge_count = _persist_generated_edges(
            store,
            generated,
            allowed_endpoints=_semantic_edge_allowed_endpoints_from_rows(query, rows),
            case_grounding=_semantic_edge_grounding_from_rows(rows),
            provenance={
                "provider": config.provider,
                "model": config.preferred,
                "job_id": job_id,
                "mode": "query",
                "query": query,
            },
        )
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
        "graph": global_graph(db_path, limit=limits.int_value("semantic", "post_batch_graph_edge_budget", minimum=1)),
    }


def generate_semantic_edges_batch(
    db_path: Path,
    limit: Optional[int] = None,
    batch_size: Optional[int] = None,
    edge_provider: Optional[EdgeProvider] = None,
    include_evidence_derived: bool = False,
    evidence_row_cap: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate semantic edges from indexed corpus candidates and persist them."""

    limits = load_workbench_limits()
    configured_candidate_limit = limits.int_value("semantic", "batch_candidate_limit", minimum=1)
    configured_batch_size = limits.int_value("semantic", "batch_size", minimum=1)
    configured_overfetch_multiplier = limits.int_value("semantic", "candidate_overfetch_multiplier", minimum=1)
    post_batch_graph_limit = limits.int_value("semantic", "post_batch_graph_edge_budget", minimum=1)
    if configured_candidate_limit is None or configured_batch_size is None or configured_overfetch_multiplier is None:
        raise ValueError(f"semantic batch limits are missing from {limits.path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    provider_settings = load_provider_settings(db_path)
    config = _edge_provider_config(provider_settings)
    if config is None:
        raise ValueError("edge provider settings are missing")
    candidate_limit = max(1, int(limit if limit is not None else configured_candidate_limit))
    batch_size = max(1, int(batch_size if batch_size is not None else configured_batch_size))
    candidates = _semantic_edge_batch_candidates(
        store,
        limit=candidate_limit,
        overfetch_multiplier=configured_overfetch_multiplier,
    )
    if not candidates:
        raise ValueError("no indexed semantic edge candidates found")
    job_id = store.start_job(
        "semantic_edges_batch",
        f"Generating semantic edges from {len(candidates)} indexed candidates",
        metadata={
            "mode": "batch",
            "candidate_count": len(candidates),
            "batch_size": batch_size,
            "candidate_overfetch_multiplier": configured_overfetch_multiplier,
            "provider_settings": provider_settings,
        },
    )
    provider = edge_provider or create_edge_provider(config)
    edge_count = 0
    try:
        for start in range(0, len(candidates), batch_size):
            batch = candidates[start : start + batch_size]
            prompt = _semantic_edge_batch_prompt(batch)
            try:
                generated = normalize_generated_cases(provider.generate(prompt, config))
            except (TypeError, ValueError, json.JSONDecodeError):
                generated = {"cases": []}
            persisted = _persist_generated_edges(
                store,
                generated,
                allowed_endpoints=_semantic_edge_allowed_endpoints_from_candidates(batch),
                case_grounding=_semantic_edge_grounding_from_candidates(batch),
                provenance={
                    "provider": config.provider,
                    "model": config.preferred,
                    "job_id": job_id,
                    "mode": "batch",
                },
                commit=False,
            )
            if persisted <= 0 and len(batch) > 1:
                for candidate in batch:
                    single_batch = [candidate]
                    single_prompt = _semantic_edge_batch_prompt(single_batch)
                    try:
                        single_generated = normalize_generated_cases(provider.generate(single_prompt, config))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        continue
                    persisted += _persist_generated_edges(
                        store,
                        single_generated,
                        allowed_endpoints=_semantic_edge_allowed_endpoints_from_candidates(single_batch),
                        case_grounding=_semantic_edge_grounding_from_candidates(single_batch),
                        provenance={
                            "provider": config.provider,
                            "model": config.preferred,
                            "job_id": job_id,
                            "mode": "batch",
                            "fallback_batch_size": 1,
                        },
                        commit=False,
                    )
            edge_count += persisted
        if edge_count <= 0:
            raise ValueError("semantic edge provider returned no persistable edges")
        store.con.commit()
        store.finish_job(job_id, "generated", f"Generated {edge_count} semantic edges from {len(candidates)} candidates")
    except Exception as exc:
        store.con.rollback()
        store.finish_job(job_id, "failed", str(exc))
        raise
    return {
        "source": "semantic_edge_batch_job",
        "db_path": str(db_path),
        "provider": config.provider,
        "model": config.preferred,
        "candidate_count": len(candidates),
        "candidate_overfetch_multiplier": configured_overfetch_multiplier,
        "batch_size": batch_size,
        "edge_count": edge_count,
        "job_id": job_id,
        "graph": global_graph(
            db_path,
            limit=post_batch_graph_limit,
            include_evidence_derived=include_evidence_derived,
            evidence_row_cap=evidence_row_cap,
        ),
    }


def generate_doc_nodes_batch(
    db_path: Path,
    limit: Optional[int] = None,
    batch_size: Optional[int] = None,
    edge_provider: Optional[EdgeProvider] = None,
) -> Dict[str, Any]:
    """Use the configured LLM provider to extract BoxMatrix-style doc nodes."""

    limits = load_workbench_limits()
    configured_candidate_limit = limits.int_value("semantic", "batch_candidate_limit", minimum=1)
    configured_batch_size = limits.int_value("semantic", "batch_size", minimum=1)
    post_batch_graph_limit = limits.int_value("semantic", "post_batch_graph_edge_budget", minimum=1)
    if configured_candidate_limit is None or configured_batch_size is None:
        raise ValueError(f"semantic batch limits are missing from {limits.path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    provider_settings = load_provider_settings(db_path)
    config = _edge_provider_config(provider_settings)
    if config is None:
        raise ValueError("edge provider settings are missing")
    candidate_limit = max(1, int(limit if limit is not None else configured_candidate_limit))
    requested_batch_size = max(1, int(batch_size if batch_size is not None else configured_batch_size))
    batch_size = _doc_node_effective_batch_size(requested_batch_size, config)
    candidates = _doc_node_candidates(store, limit=candidate_limit)
    if not candidates:
        raise ValueError("no indexed document candidates found")
    candidate_by_id = {str(candidate["id"]): candidate for candidate in candidates}
    job_id = store.start_job(
        "doc_nodes_batch",
        f"Extracting doc boxes from {len(candidates)} document candidates",
        metadata={
            "mode": "doc_nodes_batch",
            "candidate_count": len(candidates),
            "batch_size": batch_size,
            "provider_settings": provider_settings,
        },
    )
    provider = edge_provider or create_doc_node_provider(config)
    box_count = 0
    edge_count = 0
    try:
        for start in range(0, len(candidates), batch_size):
            batch = candidates[start : start + batch_size]
            prompt = _doc_node_batch_prompt(batch)
            generated: Mapping[str, Any] = {}
            batch_failed = False
            try:
                generated = provider.generate(prompt, config)
            except Exception:
                batch_failed = True
            persisted = {"boxes": 0, "edges": 0}
            if not batch_failed:
                persisted = _persist_doc_nodes(
                    store,
                    generated,
                    candidate_by_id,
                    provenance={
                        "provider": config.provider,
                        "model": config.preferred,
                        "job_id": job_id,
                        "mode": "doc_nodes_batch",
                    },
                )
            box_count += persisted["boxes"]
            edge_count += persisted["edges"]
            if (batch_failed or persisted["boxes"] <= 0) and len(batch) > 1:
                for candidate in batch:
                    single_prompt = _doc_node_batch_prompt([candidate])
                    try:
                        single_generated = provider.generate(single_prompt, config)
                    except Exception:
                        continue
                    single_persisted = _persist_doc_nodes(
                        store,
                        single_generated,
                        candidate_by_id,
                        provenance={
                            "provider": config.provider,
                            "model": config.preferred,
                            "job_id": job_id,
                            "mode": "doc_nodes_batch",
                            "fallback_batch_size": 1,
                        },
                    )
                    box_count += single_persisted["boxes"]
                    edge_count += single_persisted["edges"]
        if box_count <= 0 or edge_count <= 0:
            raise ValueError("doc node provider returned no persistable boxes")
        store.con.commit()
        store.finish_job(job_id, "generated", f"Generated {box_count} doc boxes from {len(candidates)} candidates")
    except Exception as exc:
        store.con.rollback()
        store.finish_job(job_id, "failed", str(exc))
        raise
    return {
        "source": "doc_node_batch_job",
        "db_path": str(db_path),
        "provider": config.provider,
        "model": config.preferred,
        "candidate_count": len(candidates),
        "batch_size": batch_size,
        "box_count": box_count,
        "edge_count": edge_count,
        "job_id": job_id,
        "graph": global_graph(db_path, limit=post_batch_graph_limit),
    }


def _doc_node_effective_batch_size(requested_batch_size: int, config: EdgeModelConfig) -> int:
    if config.num_ctx < DOC_NODE_MULTI_BATCH_MIN_CTX or config.num_predict < DOC_NODE_MULTI_BATCH_MIN_PREDICT:
        return 1
    return min(DOC_NODE_MAX_BATCH_SIZE, max(1, requested_batch_size))


def add_resolver_profile(
    db_path: Path,
    profile_id: str,
    language: str,
    wrappers: Iterable[str],
    strategy: str,
    path: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    config_path = _resolve_resolver_config_path(path or f"configs/resolvers/{profile_id}.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"resolver config must exist: {config_path}")
    config_profile = load_resolver_profile(config_path)
    if config_profile.id != profile_id:
        raise ValueError(f"resolver config id {config_profile.id!r} does not match profile id {profile_id!r}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    wrapper_list = list(config_profile.wrappers) or list(config_profile.python_extractors) or list(wrappers)
    store.upsert_resolver_profile(
        profile_id,
        config_profile.language or language,
        wrapper_list,
        strategy,
        str(path),
        enabled,
        config=resolver_profile_to_config(config_profile),
    )
    return {
        "id": profile_id,
        "language": config_profile.language or language,
        "wrappers": wrapper_list,
        "strategy": strategy,
        "path": path,
        "enabled": enabled,
    }


def _resolve_resolver_config_path(path: str) -> Path:
    config_path = Path(path)
    if config_path.is_absolute():
        return config_path
    return Path.cwd() / config_path


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
    profile = resolver_profile_from_config(
        profile_data.get("config", {}),
        fallback_id=str(profile_data["id"]),
        fallback_language=language,
        fallback_wrappers=wrappers,
        fallback_strategy=str(profile_data["strategy"]),
    )
    resolved_items = (
        [resolved] if (resolved := resolve_python_symbol(source, profile)) else []
    ) if language == "python" else resolve_cpp_register_calls(source, profile)
    symbols = []
    for resolved in resolved_items:
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
    symbols = _evidence_symbols_for_chunk(chunk.text, queries, resolver_profiles or [], chunk.source_type)
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
            commit=False,
        )
    if count:
        store.con.commit()
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
    options = edge.get("options")
    if not isinstance(options, Mapping):
        options = {}

    def option_value(name: str, default: object) -> object:
        if name in edge and edge.get(name) not in (None, ""):
            return edge.get(name)
        if name in options and options.get(name) not in (None, ""):
            return options.get(name)
        return default

    return EdgeModelConfig(
        preferred=model,
        fallback=str(edge.get("fallback_model") or edge.get("fallback") or ""),
        provider=str(edge.get("provider") or "ollama"),
        api_base_url=str(edge.get("api_base_url") or edge.get("base_url") or "http://localhost:11434"),
        api_path=str(edge.get("api_path") or ""),
        extra_headers={str(key): str(value) for key, value in dict(headers).items()},
        format=str(edge.get("format") or "json"),
        num_ctx=int(option_value("num_ctx", 2048)),
        num_predict=int(option_value("num_predict", 256)),
        temperature=float(option_value("temperature", 0)),
        keep_alive=str(edge.get("keep_alive") or "0s"),
        think=bool(edge.get("think", False)),
        timeout_seconds=int(edge.get("timeout_seconds") or 60),
    )


def _chunks_missing_provider_embedding(
    store: AsipStore,
    provider: str,
    model: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    sql = """
        select chunks.id, chunks.text
        from chunks
        left join embeddings
          on embeddings.chunk_id = chunks.id
        where embeddings.chunk_id is null
           or embeddings.provider != ?
           or embeddings.model != ?
           or coalesce(json_extract(embeddings.metadata_json, '$.source'), '') in ('deterministic', 'deterministic-fallback')
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
            *[token.upper() for token in _query_tokens(query) if _is_semantic_raw_edge_endpoint(token)],
            *[
                str(row.get("symbol") or "")
                for row in row_list
                if _is_semantic_raw_edge_endpoint(str(row.get("symbol") or ""), str(row.get("entity_type") or ""))
            ],
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


def _semantic_edge_batch_candidates(
    store: AsipStore,
    limit: int,
    overfetch_multiplier: int = 1,
) -> List[Dict[str, Any]]:
    row_limit = max(1, int(limit)) * max(1, int(overfetch_multiplier))
    rows = store.con.execute(
        """
        select
          evidence.chunk_id,
          evidence.source_type,
          evidence.path,
          evidence.line_start,
          evidence.line_end,
          evidence.page,
          evidence.symbol,
          evidence.entity_type,
          evidence.access_type,
          evidence.confidence,
          evidence.snippet,
          chunks.text as chunk_text
        from evidence
        join chunks on chunks.id = evidence.chunk_id
        order by evidence.confidence desc, evidence.id asc
        limit ?
        """,
        (row_limit,),
    ).fetchall()
    candidates: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        symbol = str(row["symbol"] or "").strip()
        if not symbol or not _is_semantic_raw_edge_endpoint(symbol, str(row["entity_type"] or "")):
            continue
        candidate_id = _semantic_edge_candidate_id(row)
        candidate = candidates.setdefault(
            candidate_id,
            {
                "id": candidate_id,
                "source_type": str(row["source_type"] or ""),
                "path": str(row["path"] or ""),
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "page": row["page"],
                "terms": [],
                "term_types": {},
                "snippets": [],
                "graph_context": [],
            },
        )
        if symbol not in candidate["terms"]:
            candidate["terms"].append(symbol)
        candidate["term_types"][symbol] = str(row["entity_type"] or "")
        snippet = str(row["snippet"] or row["chunk_text"] or "").strip()
        if snippet and snippet not in candidate["snippets"]:
            candidate["snippets"].append(snippet[:500])
        _augment_semantic_edge_candidate_with_graph_context(store, candidate)
    ranked = [
        candidate
        for candidate in candidates.values()
        if len(candidate.get("terms") or []) >= 1 and (candidate.get("snippets") or [])
    ]
    ranked.sort(key=lambda item: (-len(item.get("terms") or []), str(item["id"])))
    return ranked[: max(1, int(limit))]


def _augment_semantic_edge_candidate_with_graph_context(store: AsipStore, candidate: Dict[str, Any]) -> None:
    if str(candidate.get("source_type") or "") != "code":
        return
    path = str(candidate.get("path") or "")
    line_start = _optional_int(candidate.get("line_start"))
    line_end = _optional_int(candidate.get("line_end")) or line_start
    if not path or not line_start:
        return
    terms = [str(term) for term in candidate.get("terms", []) or [] if str(term or "").strip()]
    term_lookup = {term.lower() for term in terms}
    rows = store.con.execute(
        """
        select src, dst, relation, provenance_json
        from edges
        where stage = 'deterministic'
          and path = ?
          and line_start between ? and ?
        order by abs(coalesce(line_start, ?) - ?), id asc
        limit 80
        """,
        (path, max(1, line_start - 2), int(line_end) + 2, line_start, line_start),
    ).fetchall()
    for row in rows:
        src = str(row["src"] or "").strip()
        dst = str(row["dst"] or "").strip()
        provenance = _json_object(str(row["provenance_json"] or "{}"))
        field = str(provenance.get("field") or "").strip()
        if term_lookup and not ({src.lower(), dst.lower(), field.lower()} & term_lookup):
            continue
        for endpoint in (src, dst):
            product_kind = product_endpoint_kind(endpoint)
            if product_kind in {"function", "register", "doc"}:
                _add_semantic_candidate_term(candidate, endpoint, product_kind, prepend=product_kind == "function")
        if product_endpoint_kind(src) == "function" and product_endpoint_kind(dst) == "register":
            fact = f"{src} {str(row['relation'] or 'relates_to').strip() or 'relates_to'} {dst}"
            graph_context = candidate.setdefault("graph_context", [])
            if fact not in graph_context:
                graph_context.append(fact)


def _add_semantic_candidate_term(
    candidate: Dict[str, Any],
    term: str,
    entity_type: str,
    prepend: bool = False,
) -> None:
    endpoint = term.strip()
    if not endpoint:
        return
    terms = candidate.setdefault("terms", [])
    if endpoint not in terms:
        if prepend:
            terms.insert(0, endpoint)
        else:
            terms.append(endpoint)
    term_types = candidate.setdefault("term_types", {})
    if isinstance(term_types, dict):
        term_types.setdefault(endpoint, entity_type)


def _semantic_edge_batch_prompt(candidates: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "Generate potential ASIP semantic graph edges from indexed corpus candidates.",
        "Return JSON cases with edges containing src, relation, dst, confidence, and evidence.",
        "Return compact JSON only. Keep each evidence value under 140 characters and quote only the smallest supporting phrase, not whole source lines.",
        "Use only exact CASE ids, exact TERMS, or exact function/register/doc symbols shown in the prompt for src and dst.",
        "Edges with endpoints outside CASE ids or TERMS are discarded.",
        "Do not create local-variable endpoints such as tmp, ret, data, value, reg, or ring.",
        "For code CASEs, prefer GRAPH_CONTEXT function/register facts over assignment target variables.",
        "Return at most two edges per CASE; prefer direct writes or reads over field-level variants.",
    ]
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "candidate")
        terms = ", ".join(str(term) for term in candidate.get("terms", []) if term)
        source = _semantic_edge_candidate_source(candidate)
        lines.extend(
            [
                f"CASE {candidate_id}",
                f"SOURCE: {source}",
                f"TERMS: {terms}",
                "SNIPPET:",
            ]
        )
        snippets = list(candidate.get("snippets", []) or [])
        graph_context = [str(item) for item in candidate.get("graph_context", []) or [] if item]
        for index, fact in enumerate(graph_context[:5], start=1):
            lines.append(f"GRAPH_CONTEXT {index}: {fact}")
        for index, snippet in enumerate(snippets[:3], start=1):
            lines.append(f"{index}: {snippet}")
    return "\n".join(lines)


def _doc_node_candidates(store: AsipStore, limit: int) -> List[Dict[str, Any]]:
    rows = store.con.execute(
        """
        select
          chunks.id as chunk_id,
          documents.source_type,
          documents.path,
          chunks.line_start,
          chunks.line_end,
          chunks.page,
          chunks.text as chunk_text,
          count(evidence.id) as evidence_count,
          coalesce(sum(case when evidence.entity_type = 'register' then 1 else 0 end), 0) as register_evidence_count,
          coalesce(sum(case when evidence.entity_type = 'function' then 1 else 0 end), 0) as function_evidence_count
        from chunks
        join documents on documents.id = chunks.document_id
        left join evidence on evidence.chunk_id = chunks.id
        where documents.source_type in ('doc', 'pdf')
        group by chunks.id
        order by register_evidence_count desc,
                 function_evidence_count desc,
                 evidence_count desc,
                 chunks.id asc
        limit ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    rows = sorted(
        rows,
        key=lambda row: (
            -int(row["register_evidence_count"] or 0),
            -int(row["function_evidence_count"] or 0),
            -int(row["evidence_count"] or 0),
            int(row["chunk_id"] or 0),
        ),
    )[: max(1, int(limit))]
    terms_by_chunk = _doc_node_candidate_terms(store, [int(row["chunk_id"]) for row in rows])
    candidates = []
    for row in rows:
        candidate = {
            "chunk_id": row["chunk_id"],
            "source_type": str(row["source_type"] or ""),
            "path": str(row["path"] or ""),
            "line_start": row["line_start"],
            "line_end": row["line_end"],
            "page": row["page"],
            "chunk_text": str(row["chunk_text"] or ""),
            "evidence_count": int(row["evidence_count"] or 0),
            "register_evidence_count": int(row["register_evidence_count"] or 0),
            "function_evidence_count": int(row["function_evidence_count"] or 0),
        }
        candidate["id"] = _semantic_edge_candidate_id(candidate)
        candidate_terms = terms_by_chunk.get(int(row["chunk_id"] or 0), {})
        candidate["terms"] = list(candidate_terms.keys())
        candidate["term_types"] = candidate_terms
        candidates.append(candidate)
    return candidates


def _doc_node_candidate_terms(store: AsipStore, chunk_ids: Iterable[int], per_chunk_limit: int = 24) -> Dict[int, Dict[str, str]]:
    ids = [int(chunk_id) for chunk_id in chunk_ids if int(chunk_id)]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = store.con.execute(
        f"""
        select chunk_id, symbol, entity_type, confidence, id
        from evidence
        where chunk_id in ({placeholders})
        order by chunk_id asc, confidence desc, id asc
        """,
        ids,
    ).fetchall()
    terms_by_chunk: Dict[int, Dict[str, str]] = {}
    for row in rows:
        chunk_id = int(row["chunk_id"])
        terms = terms_by_chunk.setdefault(chunk_id, {})
        if len(terms) >= per_chunk_limit:
            continue
        symbol = str(row["symbol"] or "").strip()
        entity_type = str(row["entity_type"] or "").strip()
        if not symbol or symbol in terms:
            continue
        if not _is_semantic_raw_edge_endpoint(symbol, entity_type):
            continue
        terms[symbol] = entity_type
    return terms_by_chunk


def _doc_node_batch_prompt(candidates: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "Use an LLM call to extract ASIP document graph nodes. Do not use a skill.",
        "Follow the BoxMatrix idea: a Box is a self-contained concept, requirement, register behavior, workflow, or constraint; the Matrix is the relationship network between boxes and indexed hardware symbols.",
        "Return only JSON with documents, boxes, and relationships.",
        "Schema: {\"documents\":[{\"id\":string,\"boxes\":[{\"id\":string,\"name\":string,\"summary\":string,\"inputs\":[string],\"outputs\":[string],\"constraints\":[string],\"confidence\":number,\"evidence\":string}],\"relationships\":[{\"src\":string,\"relation\":string,\"dst\":string,\"confidence\":number,\"evidence\":string}]}]}",
        "Keep summaries, inputs, outputs, constraints, and evidence compact. Each evidence value must stay under 140 characters.",
        "Relationship src/dst may use a box id from the same document, a document section id, a code function, or a register symbol found in text. Register fields must be recorded in box inputs/outputs/constraints, not as relationship endpoints.",
        "Return at most one box and one relationship per document. Prefer the strongest hardware concept or register behavior.",
        "Every documents[].id must exactly match one DOCUMENT id below.",
        "Prefer LINKED SYMBOLS for relationship endpoints; do not invent symbols that are not in the document text or LINKED SYMBOLS.",
    ]
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "document")
        source = _semantic_edge_candidate_source(candidate)
        lines.extend([f"DOCUMENT {candidate_id}", f"SOURCE: {source}", "TEXT:"])
        terms = [str(term) for term in candidate.get("terms", []) or [] if term]
        term_types = candidate.get("term_types") if isinstance(candidate.get("term_types"), Mapping) else {}
        if terms:
            annotated_terms = [
                f"{term} ({str(term_types.get(term) or 'symbol')})"
                for term in terms[:DOC_NODE_PROMPT_TERM_LIMIT]
            ]
            lines.append(f"LINKED SYMBOLS: {', '.join(annotated_terms)}")
        else:
            lines.append("LINKED SYMBOLS: none")
        text = str(candidate.get("chunk_text") or "").strip()
        lines.append(text[:DOC_NODE_PROMPT_TEXT_CHARS])
    return "\n".join(lines)


def _persist_doc_nodes(
    store: AsipStore,
    generated: Mapping[str, Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    provenance: Mapping[str, object],
) -> Dict[str, int]:
    box_count = 0
    edge_count = 0
    for document in generated.get("documents", []):
        if not isinstance(document, Mapping):
            continue
        document_id = str(document.get("id") or "").strip()
        if document_id not in candidates_by_id:
            continue
        candidate = candidates_by_id[document_id]
        local_boxes: Dict[str, str] = {}
        for box in document.get("boxes", []):
            if not isinstance(box, Mapping):
                continue
            box_node_id = _doc_box_node_id(candidate, box)
            if not box_node_id or not is_graph_entity_endpoint(box_node_id):
                continue
            local_id = str(box.get("id") or box.get("name") or "").strip()
            if local_id:
                local_boxes[local_id] = box_node_id
            confidence = float(box.get("confidence") or 0.82)
            edge_id = store.add_edge(
                src=document_id,
                dst=box_node_id,
                relation="contains_box",
                confidence=confidence,
                stage="semantic",
                source=str(provenance.get("provider") or "llm"),
                path=str(candidate.get("path") or ""),
                line_start=_optional_int(candidate.get("line_start")),
                line_end=_optional_int(candidate.get("line_end")),
                provenance={
                    **dict(provenance),
                    "extractor": "doc_nodes",
                    "candidate_id": document_id,
                    "box_node_id": box_node_id,
                    "box_id": local_id,
                    "box_name": str(box.get("name") or local_id),
                    "summary": str(box.get("summary") or ""),
                    "inputs": list(box.get("inputs") or []),
                    "outputs": list(box.get("outputs") or []),
                    "constraints": list(box.get("constraints") or []),
                    "evidence": str(box.get("evidence") or ""),
                },
                commit=False,
            )
            if edge_id:
                box_count += 1
                edge_count += 1
        for relationship in document.get("relationships", []):
            if not isinstance(relationship, Mapping):
                continue
            src = _resolve_doc_node_endpoint(str(relationship.get("src") or ""), local_boxes)
            dst = _resolve_doc_node_endpoint(str(relationship.get("dst") or ""), local_boxes)
            if not src or not dst or src == dst:
                continue
            if not _is_semantic_graph_endpoint(src) or not _is_semantic_graph_endpoint(dst):
                continue
            box_node_id = src if src in local_boxes.values() else dst if dst in local_boxes.values() else ""
            edge_id = store.add_edge(
                src=src,
                dst=dst,
                relation=str(relationship.get("relation") or "relates_to"),
                confidence=float(relationship.get("confidence") or 0.76),
                stage="semantic",
                source=str(provenance.get("provider") or "llm"),
                path=str(candidate.get("path") or ""),
                line_start=_optional_int(candidate.get("line_start")),
                line_end=_optional_int(candidate.get("line_end")),
                provenance={
                    **dict(provenance),
                    "extractor": "doc_nodes",
                    "candidate_id": document_id,
                    "box_node_id": box_node_id,
                    "box_id": _local_box_id_for_node(local_boxes, box_node_id),
                    "box_name": _box_name_from_node_id(box_node_id),
                    "evidence": str(relationship.get("evidence") or ""),
                },
                commit=False,
            )
            if edge_id:
                edge_count += 1
    return {"boxes": box_count, "edges": edge_count}


def _doc_box_node_id(candidate: Mapping[str, Any], box: Mapping[str, Any]) -> str:
    path = str(candidate.get("path") or "").strip()
    if not path:
        return ""
    name = str(box.get("id") or box.get("name") or "box")
    return f"{path}#box-{_slug_for_semantic_candidate(name)}"


def _resolve_doc_node_endpoint(value: str, local_boxes: Mapping[str, str]) -> str:
    endpoint = value.strip()
    return local_boxes.get(endpoint, endpoint)


def _local_box_id_for_node(local_boxes: Mapping[str, str], node_id: str) -> str:
    for local_id, mapped_node_id in local_boxes.items():
        if mapped_node_id == node_id:
            return local_id
    return ""


def _box_name_from_node_id(node_id: str) -> str:
    anchor = node_id.partition("#")[2]
    if anchor.startswith("box-"):
        return anchor.removeprefix("box-").replace("-", " ").strip()
    return ""


def _optional_int(value: Any) -> Optional[int]:
    return int(value) if value not in (None, "") else None


def _persist_generated_edges(
    store: AsipStore,
    generated: Mapping[str, Any],
    provenance: Optional[Mapping[str, object]] = None,
    commit: bool = True,
    allowed_endpoints: Optional[set[str]] = None,
    case_grounding: Optional[Mapping[str, List[Mapping[str, Any]]]] = None,
) -> int:
    edge_count = 0
    seen_edges: set[tuple[str, str, str]] = set()
    for case in generated.get("cases", []):
        if not isinstance(case, Mapping):
            continue
        case_id = str(case.get("id") or "").strip()
        source_refs = list((case_grounding or {}).get(case_id, []))
        for edge in case.get("edges", []):
            if not isinstance(edge, Mapping):
                continue
            src = str(edge.get("src") or "").strip()
            dst = str(edge.get("dst") or "").strip()
            raw_relation = str(edge.get("relation") or "relates_to").strip()
            relation = normalize_product_relation(raw_relation)
            if not src or not dst:
                continue
            if not relation:
                continue
            if src == dst:
                continue
            if allowed_endpoints is not None and (src not in allowed_endpoints or dst not in allowed_endpoints):
                continue
            if not is_graph_entity_endpoint(src) or not is_graph_entity_endpoint(dst):
                continue
            edge_key = (src, relation.lower(), dst)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edge_id = store.add_edge(
                src=src,
                dst=dst,
                relation=relation,
                confidence=float(edge.get("confidence") or 0.5),
                stage="semantic",
                source=str((provenance or {}).get("provider") or "llm"),
                provenance={
                    **dict(provenance or {}),
                    "extractor": "semantic_edges",
                    "evidence": str(edge.get("evidence") or ""),
                    **({"case_id": case_id} if case_id else {}),
                    **({"source_refs": source_refs} if source_refs else {}),
                    **({"original_relation": raw_relation} if raw_relation != relation else {}),
                },
                commit=False,
            )
            if edge_id:
                edge_count += 1
    if edge_count and commit:
        store.con.commit()
    return edge_count


def _semantic_edge_allowed_endpoints_from_rows(query: str, rows: Iterable[Mapping[str, Any]]) -> set[str]:
    row_list = list(rows)
    endpoint_types: Dict[str, str] = {}
    for token in _query_tokens(query):
        if _is_semantic_graph_endpoint(token):
            endpoint_types[token] = ""
    for row in row_list:
        symbol = str(row.get("symbol") or "").strip()
        entity_type = str(row.get("entity_type") or "").strip()
        if _is_semantic_raw_edge_endpoint(symbol, entity_type):
            endpoint_types[symbol] = entity_type
    return {
        endpoint
        for endpoint in _unique_ordered(endpoint_types.keys())
        if endpoint and _is_semantic_raw_edge_endpoint(endpoint, endpoint_types.get(endpoint, ""))
    }


def _semantic_edge_allowed_endpoints_from_candidates(candidates: Iterable[Mapping[str, Any]]) -> set[str]:
    endpoints: set[str] = set()
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "").strip()
        if candidate_id and _is_semantic_graph_endpoint(candidate_id):
            endpoints.add(candidate_id)
        term_types = candidate.get("term_types") if isinstance(candidate.get("term_types"), Mapping) else {}
        for term in candidate.get("terms", []) or []:
            endpoint = str(term or "").strip()
            entity_type = str(term_types.get(endpoint) or "") if isinstance(term_types, Mapping) else ""
            if endpoint and _is_semantic_raw_edge_endpoint(endpoint, entity_type):
                endpoints.add(endpoint)
    return endpoints


def _semantic_edge_grounding_from_rows(rows: Iterable[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    refs = [_semantic_edge_source_ref(row) for row in rows]
    return {"workbench-query": [ref for ref in refs if ref]}


def _semantic_edge_grounding_from_candidates(candidates: Iterable[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    grounding: Dict[str, List[Mapping[str, Any]]] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "").strip()
        if not candidate_id:
            continue
        ref = _semantic_edge_source_ref(candidate)
        if ref:
            grounding[candidate_id] = [ref]
    return grounding


def _semantic_edge_source_ref(row: Mapping[str, Any]) -> Dict[str, Any]:
    ref: Dict[str, Any] = {
        "source_type": str(row.get("source_type") or ""),
        "path": str(row.get("path") or ""),
    }
    for key in ("corpus_id", "repo", "line_start", "line_end", "page"):
        value = row.get(key)
        if value not in (None, ""):
            ref[key] = value
    terms = [str(term) for term in row.get("terms", []) or [] if term] if isinstance(row.get("terms", []), list) else []
    if terms:
        ref["terms"] = terms
    return {key: value for key, value in ref.items() if value not in ("", [], {})}


def _is_semantic_raw_edge_endpoint(endpoint: str, entity_type: str = "") -> bool:
    if _is_semantic_graph_endpoint(endpoint, entity_type):
        return True
    value = endpoint.strip()
    if not value or not is_graph_entity_endpoint(value):
        return False
    kind = entity_type.strip().lower() or _entity_type_for_symbol(value)
    return kind == "field"


def _is_semantic_graph_endpoint(endpoint: str, entity_type: str = "") -> bool:
    value = endpoint.strip()
    if not value or not is_graph_entity_endpoint(value):
        return False
    product_kind = product_endpoint_kind(value)
    if not product_kind:
        return False
    kind = entity_type.strip().lower()
    if kind:
        if kind in {"doc_section", "pdf_section", "doc_box"}:
            return product_kind == "doc"
        if kind in {"function", "register", "doc"}:
            return product_kind == kind
        return False
    return product_kind in {"function", "register", "doc"}


def _semantic_edge_candidate_id(row: Mapping[str, Any]) -> str:
    source_type = str(row["source_type"] or "")
    path = str(row["path"] or "candidate")
    text = str(row["chunk_text"] or "")
    if source_type in {"doc", "pdf"}:
        heading = _first_markdown_heading_for_semantic_candidate(text)
        if heading:
            return f"{path}#{_slug_for_semantic_candidate(heading)}"
        page = int(row["page"] or 0)
        if page:
            return f"{path}#page-{page}"
    line_start = int(row["line_start"] or 0)
    line_end = int(row["line_end"] or line_start or 0)
    if line_start:
        return f"{path}#lines-{line_start}-{line_end}"
    return f"{path}#chunk-{row['chunk_id']}"


def _semantic_edge_candidate_source(candidate: Mapping[str, Any]) -> str:
    path = str(candidate.get("path") or "unknown")
    if candidate.get("page"):
        return f"{path}:page {candidate['page']}"
    if candidate.get("line_start"):
        line_start = candidate.get("line_start")
        line_end = candidate.get("line_end") or line_start
        return f"{path}:lines {line_start}-{line_end}"
    return path


def _first_markdown_heading_for_semantic_candidate(text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(?:\d+:\s*)?#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip().strip("#").strip()
    return ""


def _slug_for_semantic_candidate(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    return slug or "section"


def _index_deterministic_code_graph_edges(
    store: AsipStore,
    file_path: Path,
    source_root: Path,
    resolver_profiles: Iterable[ResolverProfile],
    corpus_id: str = "",
    repo: str = "",
) -> int:
    return _index_deterministic_code_graph_files(
        store,
        [file_path],
        source_root,
        resolver_profiles,
        corpus_id=corpus_id,
        repo=repo,
    )


def _index_deterministic_code_graph_files(
    store: AsipStore,
    file_paths: Iterable[Path],
    source_root: Path,
    resolver_profiles: Iterable[ResolverProfile],
    corpus_id: str = "",
    repo: str = "",
) -> int:
    profiles = [profile for profile in resolver_profiles if profile.language in {"c", "cpp", "c++"}]
    if not profiles:
        return 0
    file_path_list = list(file_paths)
    function_locations: Dict[str, List[CodeGraphFunctionLocation]] = {}
    table_field_aliases: Dict[str, List[str]] = {}
    version_field_sinks: Dict[str, List[CodeGraphVersionFieldSink]] = {}
    receiver_table_aliases: Dict[str, List[str]] = {}
    return_table_aliases: Dict[str, List[str]] = {}
    for file_path in file_path_list:
        for location in collect_code_graph_function_locations(file_path, source_root=source_root):
            function_locations.setdefault(location.name, []).append(location)
        for alias_key, alias_values in collect_code_graph_table_field_aliases(file_path, source_root=source_root).items():
            table_field_aliases.setdefault(str(alias_key), [])
            for alias_value in alias_values:
                alias_text = str(alias_value)
                if alias_text not in table_field_aliases[str(alias_key)]:
                    table_field_aliases[str(alias_key)].append(alias_text)
        for sink_key, sinks in collect_code_graph_version_field_sinks(file_path, source_root=source_root).items():
            version_field_sinks.setdefault(str(sink_key), [])
            for sink in sinks:
                if sink not in version_field_sinks[str(sink_key)]:
                    version_field_sinks[str(sink_key)].append(sink)
        for alias_key, alias_values in collect_code_graph_return_table_aliases(file_path, source_root=source_root).items():
            return_table_aliases.setdefault(str(alias_key), [])
            for alias_value in alias_values:
                alias_text = str(alias_value)
                if alias_text not in return_table_aliases[str(alias_key)]:
                    return_table_aliases[str(alias_key)].append(alias_text)
    return_table_aliases = {
        alias_key: alias_values
        for alias_key, alias_values in return_table_aliases.items()
        if len(alias_values) == 1
    }
    for file_path in file_path_list:
        for alias_key, alias_values in collect_code_graph_receiver_table_aliases(
            file_path,
            version_field_sinks,
            source_root=source_root,
        ).items():
            receiver_table_aliases.setdefault(str(alias_key), [])
            for alias_value in alias_values:
                alias_text = str(alias_value)
                if alias_text not in receiver_table_aliases[str(alias_key)]:
                    receiver_table_aliases[str(alias_key)].append(alias_text)
    graphs = []
    count = 0
    seen: set[tuple[str, str, str, str, int, int]] = set()
    for file_path in file_path_list:
        try:
            graph = build_deterministic_code_graph(
                file_path,
                source_root=source_root,
                resolver_profiles=profiles,
                known_function_locations=function_locations,
                known_table_field_aliases=table_field_aliases,
                known_version_field_sinks=version_field_sinks,
                known_receiver_table_aliases=receiver_table_aliases,
                known_return_table_aliases=return_table_aliases,
            )
        except Exception as exc:
            raise RuntimeError(f"deterministic code graph failed for {file_path}: {exc}") from exc
        graphs.append(graph)
        for edge in graph.edges:
            count += _persist_code_graph_edge(
                store,
                edge,
                seen,
                corpus_id=corpus_id,
                repo=repo,
                resolver_profile_ids=[profile.id for profile in profiles],
            )

    callbacks_by_slot: Dict[str, List[Any]] = {}
    for graph in graphs:
        for callback in graph.callback_slots:
            callbacks_by_slot.setdefault(str(callback.slot), []).append(callback)
    for graph in graphs:
        for slot_call in graph.slot_calls:
            callbacks = _callbacks_for_code_graph_slot_call(slot_call, callbacks_by_slot)
            call_kind = _code_graph_callback_call_kind(slot_call, callbacks)
            dispatch_scope = _code_graph_callback_dispatch_scope(slot_call, callbacks, call_kind)
            callback_ambiguous = dispatch_scope == "ambiguous"
            confidence = 0.72 if call_kind == "vtable_dispatch" else 0.82
            for callback in callbacks:
                if str(callback.function) == str(slot_call.caller):
                    continue
                count += _persist_code_graph_edge(
                    store,
                    _CodeGraphEdgeRecord(
                        src=str(slot_call.caller),
                        dst=str(callback.function),
                        relation="calls",
                        confidence=confidence,
                        stage="deterministic",
                        source="clang_callback",
                        path=str(slot_call.path),
                        line_start=slot_call.line_start,
                        line_end=slot_call.line_start,
                        provenance={
                            "extractor": "code_graph",
                            "function": str(slot_call.caller),
                            "callee": str(callback.function),
                            "call_kind": call_kind,
                            "slot": str(slot_call.slot),
                            "receiver": str(getattr(slot_call, "receiver", "") or ""),
                            "receiver_type": str(getattr(slot_call, "receiver_type", "") or ""),
                            "receiver_tables": [
                                str(table)
                                for table in getattr(slot_call, "receiver_tables", ())
                                if table
                            ],
                            "type_flow": str(getattr(slot_call, "type_flow", "") or ""),
                            "callback_table": str(callback.table),
                            "callback_table_type": str(getattr(callback, "table_type", "") or ""),
                            "callback_initializer_flow": str(getattr(callback, "initializer_flow", "") or ""),
                            "callback_candidate_count": len(callbacks),
                            "dispatch_scope": dispatch_scope,
                            "callback_ambiguous": callback_ambiguous,
                            "callee_path": str(getattr(callback, "function_path", "") or callback.path),
                            "callback_path": str(callback.path),
                            "callee_line": getattr(callback, "function_line_start", None),
                            "callback_line": getattr(callback, "assignment_line_start", None) or callback.line_start,
                        },
                    ),
                    seen,
                    corpus_id=corpus_id,
                    repo=repo,
                    resolver_profile_ids=[profile.id for profile in profiles],
                )
    if count:
        store.con.commit()
    return count


def _callbacks_for_code_graph_slot_call(
    slot_call: Any,
    callbacks_by_slot: Mapping[str, List[Any]],
) -> List[Any]:
    callbacks = callbacks_by_slot.get(str(slot_call.slot), [])
    receiver = str(getattr(slot_call, "receiver", "") or "").strip()
    if not receiver:
        return callbacks
    receiver_tables = tuple(str(table) for table in getattr(slot_call, "receiver_tables", ()) if table)
    if receiver_tables:
        exact_alias = [
            callback
            for callback in callbacks
            if str(callback.table) in receiver_tables
        ]
        return exact_alias
    receiver_leaf = _code_graph_receiver_leaf(receiver)
    exact = [callback for callback in callbacks if str(callback.table) in {receiver, receiver_leaf}]
    if exact:
        return exact
    receiver_type = str(getattr(slot_call, "receiver_type", "") or "").strip()
    table_prefixes = _code_graph_receiver_ip_block_table_prefixes(receiver)
    if receiver_type:
        typed = [
            callback
            for callback in callbacks
            if str(getattr(callback, "table_type", "") or "") == receiver_type
        ]
        narrowed = _code_graph_callbacks_matching_table_prefixes(typed, table_prefixes)
        if narrowed:
            return narrowed
        return typed
    expected_table_type = _code_graph_expected_callback_table_type(receiver)
    if expected_table_type:
        typed = [
            callback
            for callback in callbacks
            if str(getattr(callback, "table_type", "") or "") == expected_table_type
        ]
        narrowed = _code_graph_callbacks_matching_table_prefixes(typed, table_prefixes)
        if narrowed:
            return narrowed
        return typed
    if receiver_leaf in GENERIC_CALLBACK_RECEIVERS and _code_graph_slot_call_receiver_is_likely_callback(slot_call):
        return callbacks
    return []


def _code_graph_callback_call_kind(slot_call: Any, callbacks: List[Any]) -> str:
    receiver_tables = tuple(str(table) for table in getattr(slot_call, "receiver_tables", ()) if table)
    if len(receiver_tables) == 1:
        return "vtable_table_alias"
    if len(receiver_tables) > 1:
        return "vtable_dispatch"
    receiver_leaf = _code_graph_receiver_leaf(str(getattr(slot_call, "receiver", "") or ""))
    if receiver_leaf in GENERIC_CALLBACK_RECEIVERS:
        return "vtable_dispatch"
    if len(callbacks) > 1:
        return "vtable_dispatch"
    return "vtable_callback"


def _code_graph_callback_dispatch_scope(slot_call: Any, callbacks: List[Any], call_kind: str) -> str:
    if call_kind != "vtable_dispatch":
        return "matched_slot"
    receiver_tables = tuple(str(table) for table in getattr(slot_call, "receiver_tables", ()) if table)
    if len(receiver_tables) > 1 or len(callbacks) > 1:
        return "ambiguous"
    receiver_leaf = _code_graph_receiver_leaf(str(getattr(slot_call, "receiver", "") or ""))
    if receiver_leaf in GENERIC_CALLBACK_RECEIVERS:
        return "generic_slot"
    return "ambiguous"


def _code_graph_receiver_leaf(receiver: str) -> str:
    parts = re.split(r"->|\.", receiver.strip())
    leaf = parts[-1] if parts else receiver
    return re.sub(r"\[[^\]]+\]", "", leaf).strip()


def _code_graph_expected_callback_table_type(receiver: str) -> str:
    normalized = re.sub(r"\s+", "", receiver.strip())
    leaf = _code_graph_receiver_leaf(receiver)
    if leaf == "init_funcs" and "[" in normalized:
        return ""
    for suffix, table_type in CALLBACK_TYPE_BY_RECEIVER_SUFFIX:
        if normalized.endswith(suffix):
            return table_type
    return CALLBACK_TYPE_BY_RECEIVER.get(leaf, "")


def _code_graph_receiver_ip_block_table_prefixes(receiver: str) -> Tuple[str, ...]:
    normalized = re.sub(r"\s+", "", receiver)
    if "->version->funcs" not in normalized and ".version.funcs" not in normalized:
        return ()
    base = re.split(r"->|\.", normalized, maxsplit=1)[0]
    base = re.sub(r"\[[^\]]+\]", "", base).strip("&*()")
    if not base.endswith("_block"):
        return ()
    prefix = base[: -len("_block")]
    if not prefix or prefix in {"ip", "adev", "block"}:
        return ()
    return (prefix,)


def _code_graph_callbacks_matching_table_prefixes(callbacks: Iterable[Any], prefixes: Iterable[str]) -> List[Any]:
    clean_prefixes = tuple(prefix for prefix in prefixes if prefix)
    if not clean_prefixes:
        return []
    return [
        callback
        for callback in callbacks
        if any(str(getattr(callback, "table", "") or "").startswith(f"{prefix}_") for prefix in clean_prefixes)
    ]


def _code_graph_slot_call_receiver_is_likely_callback(slot_call: Any) -> bool:
    receiver = str(getattr(slot_call, "receiver", "") or "").strip()
    receiver_leaf = _code_graph_receiver_leaf(receiver)
    if receiver_leaf == "init_funcs" and "[" in receiver:
        return False
    if receiver_leaf in {"init_func", "init_funcs"}:
        return True
    receiver_type = str(getattr(slot_call, "receiver_type", "") or "").strip()
    return bool(receiver_type.endswith(("_funcs", "_ops", "_callbacks", "_func")))


@dataclass(frozen=True)
class _CodeGraphEdgeRecord:
    src: str
    dst: str
    relation: str
    confidence: float
    stage: str
    source: str
    path: str
    line_start: Optional[int]
    line_end: Optional[int]
    provenance: Mapping[str, object]


def _persist_code_graph_edge(
    store: AsipStore,
    edge: Any,
    seen: set[tuple[str, str, str, str, int, int]],
    corpus_id: str = "",
    repo: str = "",
    resolver_profile_ids: Optional[Iterable[str]] = None,
) -> int:
    key = (
        str(edge.src),
        str(edge.relation),
        str(edge.dst),
        str(edge.path),
        int(edge.line_start or 0),
        int(edge.line_end or 0),
    )
    if key in seen:
        return 0
    seen.add(key)
    edge_provenance = dict(edge.provenance)
    scoped_profile_ids = _unique_ordered(str(profile_id) for profile_id in (resolver_profile_ids or []))
    if "resolver_profile" not in edge_provenance and scoped_profile_ids:
        edge_provenance["resolver_profile_ids"] = scoped_profile_ids
    edge_id = store.add_edge(
        src=edge.src,
        dst=edge.dst,
        relation=edge.relation,
        confidence=edge.confidence,
        stage=edge.stage,
        source=edge.source,
        path=edge.path,
        line_start=edge.line_start,
        line_end=edge.line_end,
        provenance={
            **edge_provenance,
            **({"corpus_id": corpus_id} if corpus_id else {}),
            **({"repo": repo} if repo else {}),
        },
        commit=False,
    )
    return 1 if edge_id else 0


def _index_chunk_edges(store: AsipStore, chunk: IndexedChunk, queries: Iterable[Any]) -> int:
    count = 0
    for query in queries:
        terms = [term for term in query.expected_terms if term in chunk.text and is_graph_entity_endpoint(str(term))]
        if len(terms) < 2:
            continue
        for src, dst in zip(terms, terms[1:]):
            edge_id = store.add_edge(
                src=src,
                dst=dst,
                relation=_relation_for_terms(chunk.text, src, dst),
                confidence=0.9,
                stage="evidence",
                source="query_expected_terms",
                path=chunk.path,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                provenance={"extractor": "query_expected_terms", "query_config": True},
                commit=False,
            )
            if edge_id:
                count += 1
    if count:
        store.con.commit()
    return count


def _iter_source_files(root: Path, include: Iterable[str]) -> Iterable[Path]:
    if not root.exists():
        return []
    files: List[Path] = []
    patterns = tuple(include) or ("**/*.c", "**/*.h")
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if _is_low_signal_source_file(path):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(root).as_posix()
        if _matches_include(relative, patterns):
            files.append(path)
    return sorted(files)


def _is_low_signal_source_file(path: Path) -> bool:
    normalized = path.as_posix().lower()
    name = path.name.lower()
    if "/ucode/" in normalized and name.endswith(".h"):
        return True
    if "ucode" in name and name.endswith(("_signed.h", "_signed.c")):
        return True
    return False


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


def _normal_resolver_profile_ids(profile_ids: Optional[Iterable[str]]) -> Optional[List[str]]:
    if profile_ids is None:
        return None
    return _unique_ordered(str(profile_id).strip() for profile_id in profile_ids)


def _evidence_symbols_for_chunk(
    text: str,
    queries: Iterable[Any],
    resolver_profiles: Iterable[ResolverProfile],
    source_type: str = "",
) -> List[tuple[str, str, Optional[str], Optional[str]]]:
    found: Dict[str, tuple[str, Optional[str], Optional[str]]] = {}
    for query in queries:
        for term in query.expected_terms:
            if term in text and is_graph_entity_endpoint(str(term)):
                found[term] = (query.id, None, None)
    for identifier in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:->[A-Za-z_][A-Za-z0-9_]*)?\b", text):
        if _is_symbol_like_for_source(identifier, source_type):
            found.setdefault(identifier, ("", None, None))
    for profile in resolver_profiles:
        resolved_items = (
            [resolved] if (resolved := resolve_python_symbol(text, profile)) else []
        ) if profile.language == "python" else resolve_cpp_register_calls(text, profile)
        for resolved in resolved_items:
            if not is_graph_entity_endpoint(resolved.symbol):
                continue
            found[resolved.symbol] = (
                "",
                resolved.access,
                f"resolver profile {resolved.profile_id} -> {resolved.wrapper} -> {resolved.symbol}",
            )
    return [(symbol, *values) for symbol, values in sorted(found.items())]


def _resolver_profiles_from_store(
    store: AsipStore,
    selected_profile_ids: Optional[Iterable[str]] = None,
) -> List[ResolverProfile]:
    selected_ids = _normal_resolver_profile_ids(selected_profile_ids)
    profiles_by_id: Dict[str, ResolverProfile] = {}
    if DEFAULT_RESOLVER_PROFILE_DIR.exists():
        profiles_by_id.update(load_resolver_profiles(DEFAULT_RESOLVER_PROFILE_DIR))
    for row in store.list_resolver_profiles():
        row_id = str(row.get("id") or "")
        if not row.get("enabled", True):
            for profile_id in _resolver_profile_aliases_from_store_row(row):
                profiles_by_id.pop(profile_id, None)
            continue
        wrappers = [str(wrapper) for wrapper in row.get("wrappers", [])]
        language = str(row.get("language") or "cpp")
        access = str(row.get("strategy") or "reference")
        config = row.get("config", {})
        config_path = _resolve_resolver_config_path(str(row.get("path") or ""))
        if isinstance(config, Mapping) and config:
            profile = resolver_profile_from_config(
                config,
                fallback_id=str(row["id"]),
                fallback_language=language,
                fallback_wrappers=wrappers,
                fallback_strategy=access,
            )
        elif config_path.exists():
            profile = load_resolver_profile(config_path)
        else:
            continue
        profiles_by_id[profile.id] = profile
        if row_id and row_id != profile.id:
            profiles_by_id[row_id] = profile
    if selected_ids is not None:
        unknown_ids = [profile_id for profile_id in selected_ids if profile_id not in profiles_by_id]
        if unknown_ids:
            raise ValueError(f"unknown resolver profile id(s): {', '.join(unknown_ids)}")
        return [profiles_by_id[profile_id] for profile_id in selected_ids]
    return list(
        sorted(
            profiles_by_id.values(),
            key=lambda profile: ({"linux-amdgpu": 0, "amd-mxgpu": 1}.get(profile.id, 2), profile.id),
        )
    )


def _resolver_profiles_for_corpus(
    resolver_profiles: Iterable[ResolverProfile],
    corpus_id: str,
    repo: str,
) -> List[ResolverProfile]:
    profiles = list(resolver_profiles)
    if not profiles:
        return []
    ranked = sorted(
        enumerate(profiles),
        key=lambda item: (
            0 if _resolver_profile_matches_corpus(item[1], corpus_id, repo) else 1,
            item[0],
        ),
    )
    return [profile for _index, profile in ranked]


def _resolver_profile_matches_corpus(profile: ResolverProfile, corpus_id: str, repo: str) -> bool:
    scope = _resolver_profile_scope_tokens(corpus_id, repo)
    for value in (profile.id, *profile.aliases):
        token = _resolver_profile_scope_token(str(value))
        if token and token in scope:
            return True
    return False


def _resolver_profile_scope_tokens(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "")
        for part in [text, *re.split(r"[^A-Za-z0-9_+-]+", text)]:
            token = _resolver_profile_scope_token(part)
            if token:
                tokens.add(token)
    return tokens


def _resolver_profile_scope_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def _resolver_profile_aliases_from_store_row(row: Mapping[str, object]) -> List[str]:
    aliases = [str(row.get("id") or "")]
    profile = _resolver_profile_from_store_row(row)
    if profile is not None:
        aliases.append(profile.id)
        aliases.extend(profile.aliases)
    return _dedupe_graph_string_values(aliases)


def _resolver_profile_from_store_row(row: Mapping[str, object]) -> Optional[ResolverProfile]:
    row_id = str(row.get("id") or "")
    wrappers = [str(wrapper) for wrapper in row.get("wrappers", [])]
    language = str(row.get("language") or "cpp")
    access = str(row.get("strategy") or "reference")
    config = row.get("config", {})
    config_path = _resolve_resolver_config_path(str(row.get("path") or ""))
    try:
        if isinstance(config, Mapping) and config:
            return resolver_profile_from_config(
                config,
                fallback_id=row_id,
                fallback_language=language,
                fallback_wrappers=wrappers,
                fallback_strategy=access,
            )
        if config_path.exists():
            return load_resolver_profile(config_path)
    except Exception:
        return None
    return None


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
    if is_resolver_wrapper_name(identifier):
        return False
    if identifier in {"static", "void", "uint32_t", "return", "data"}:
        return False
    return "_" in identifier or identifier.startswith(("reg", "mm")) or identifier.isupper()


def _is_symbol_like_for_source(identifier: str, source_type: str) -> bool:
    if source_type == "register":
        return _is_register_header_symbol_like(identifier)
    return _is_symbol_like(identifier)


def _is_register_header_symbol_like(identifier: str) -> bool:
    if is_resolver_wrapper_name(identifier):
        return False
    if len(identifier) <= 2:
        return False
    if identifier.lower() in {
        "adapt",
        "data",
        "define",
        "else",
        "endif",
        "if",
        "ifdef",
        "ifndef",
        "local",
        "reg",
        "ret",
        "tmp",
        "u32",
        "uint32_t",
        "value",
    }:
        return False
    if "->" in identifier:
        return False
    for prefix in ("reg", "mm", "smn"):
        if identifier.startswith(prefix) and len(identifier) > len(prefix) and identifier[len(prefix)].isupper():
            return True
    upper = identifier.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", identifier):
        return False
    if "__" in identifier and re.search(r"(?:__|_)(MASK|SHIFT|DEFAULT)$", upper):
        return True
    if "_" not in identifier:
        return False
    register_hints = (
        "ADDR",
        "BASE",
        "CNTL",
        "CONTROL",
        "CP_HQD",
        "CP_MQD",
        "DOORBELL",
        "GRBM",
        "HQD",
        "IH_",
        "MMHUB",
        "MQD",
        "PTR",
        "QUEUE",
        "RESET",
        "RLC",
        "RPTR",
        "SDMA",
        "SIZE",
        "SMN",
        "SOFT_RESET",
        "SQ_",
        "SRBM",
        "STATUS",
        "VMID",
        "WPTR",
    )
    return any(hint in upper for hint in register_hints)


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
    if symbol.startswith(("reg", "mm", "smn")) or re.search(
        r"CNTL|CONTROL|STATUS|RESET|BASE|SIZE|VMID|DOORBELL|HQD|MQD|WPTR|RPTR|QUEUE", symbol
    ):
        return "register"
    return "function"


def _entity_type_for_source_symbol(source_type: str, symbol: str) -> str:
    if source_type == "register":
        if re.search(r"ENABLE|DISABLE|PENDING|MASK|SHIFT|RESET_REQUEST|INVALIDATE", symbol):
            return "field"
        if symbol.startswith(("WREG", "RREG", "REG_")):
            return "macro"
        if _is_register_header_symbol_like(symbol):
            return "register"
    if source_type in {"doc", "pdf"} and _is_symbol_like(symbol):
        return _entity_type_for_symbol(symbol)
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


def _resolved_chain_explanation_for_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    chain = str(row.get("resolved_chain") or "").strip()
    labels = [part.strip() for part in re.split(r"\s*->\s*", chain) if part.strip()]
    if not labels and row.get("symbol"):
        labels = [str(row["symbol"])]
    steps = [
        {
            "index": index,
            "label": label,
            "kind": _resolved_chain_step_kind(label),
        }
        for index, label in enumerate(labels, start=1)
    ]
    return {
        "evidence_id": row.get("id"),
        "symbol": row.get("symbol", ""),
        "relation": row.get("relation") or row.get("access_type") or "",
        "resolved_chain": chain,
        "steps": steps,
        "source": {
            key: row[key]
            for key in ("corpus_id", "repo", "path", "line_start", "line_end", "page", "source_type")
            if row.get(key) is not None
        },
        "snippet": row.get("snippet", ""),
    }


def _resolved_chain_step_kind(label: str) -> str:
    lowered = label.lower()
    if lowered.startswith(("read ", "write ", "source ", "resolver ", "doc ", "pdf ")):
        return "operation"
    if lowered.startswith("register "):
        return "register"
    if lowered.startswith("field "):
        return "field"
    if lowered.endswith("wrapper") or lowered in {"reg_set_field"}:
        return "resolver"
    candidate = label.split()[-1] if label.split() else label
    return _entity_type_for_symbol(candidate)


def _relation_for_terms(text: str, src: str, dst: str) -> str:
    if "REG_SET_FIELD" in text and _entity_type_for_symbol(dst) == "field":
        return "sets_field"
    if "reg_offset" in text or "BASE" in dst:
        return "maps_base"
    if re.search(r"\bWREG", text):
        return "writes"
    if re.search(r"\bRREG", text):
        return "reads"
    return "relates_to"


def _snippet_for_symbol(text: str, symbol: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if symbol in line:
            start = max(0, index - 2)
            end = min(len(lines), index + 3)
            return "\n".join(lines[start:end])
    return "\n".join(lines[:5])


def _query_tokens(query: str) -> List[str]:
    stop_words = {
        "which",
        "what",
        "where",
        "show",
        "the",
        "and",
        "for",
        "with",
        "before",
        "who",
        "write",
        "writes",
        "read",
        "reads",
        "will",
        "would",
        "can",
        "could",
        "should",
        "does",
        "do",
        "did",
        "reg",
        "regs",
        "register",
        "registers",
    }
    return [
        token
        for token in re.split(r"[^A-Za-z0-9_]+", query.lower())
        if len(token) > 2 and token not in stop_words
    ]


def _query_symbol_prefixes(query: str) -> List[str]:
    prefixes: List[str] = []
    for match in re.finditer(r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*\*)(?![A-Za-z0-9_])", query):
        raw_prefix = match.group(1)[:-1].strip()
        if len(raw_prefix.rstrip("_")) <= 2:
            continue
        for prefix in _query_symbol_prefix_variants(raw_prefix):
            lowered = prefix.lower()
            if lowered not in prefixes:
                prefixes.append(lowered)
    return prefixes


def _query_symbol_prefix_variants(prefix: str) -> List[str]:
    variants = [prefix]
    canonical = _canonical_graph_seed_symbol(prefix)
    if canonical not in variants:
        variants.append(canonical)
    return variants


def _query_token_looks_like_symbol(token: str) -> bool:
    text = str(token).strip()
    return bool(text and ("_" in text or re.search(r"\d", text)))


def _row_matches_query_symbol_prefixes(row: Dict[str, object], symbol_prefixes: List[str]) -> bool:
    symbol = str(row.get("symbol") or "")
    symbol_variants = [symbol, _canonical_graph_seed_symbol(symbol)]
    if any(
        variant.lower().startswith(prefix)
        for variant in symbol_variants
        for prefix in symbol_prefixes
    ):
        return True
    haystack = " ".join(
        str(row.get(key, ""))
        for key in ("path", "snippet", "resolved_chain")
    ).lower()
    return any(prefix in haystack for prefix in symbol_prefixes)


def _query_access_intents(query: str) -> set[str]:
    lowered = query.lower()
    intents: set[str] = set()
    if re.search(r"\bread(?:s|ing|er|ers)?\b", lowered):
        intents.add("read")
    if re.search(r"\bwrite(?:s|ing|r|rs)?\b", lowered):
        intents.add("write")
    return intents


def _access_type_matches_intents(access_type: str, access_intents: set[str]) -> bool:
    normalized = access_type.lower().replace("-", "_")
    if "read" in access_intents and normalized in {"read", "reads", "field_read", "read_modify_write"}:
        return True
    if "write" in access_intents and normalized in {"write", "writes", "field_set", "field_write", "read_modify_write"}:
        return True
    return False


def _evidence_score(
    row: Dict[str, object],
    tokens: List[str],
    fts_chunk_ids: set[int],
    access_intents: Optional[set[str]] = None,
) -> float:
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
    access_type = str(row.get("access_type") or "")
    if access_intents:
        access_priority = 2.0 if _access_type_matches_intents(access_type, access_intents) else 0.0
    else:
        access_priority = 1.0 if access_type in {"field_set", "write", "read", "read_modify_write"} else 0.0
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
    selected_sources = {str(row.get("source_type") or row.get("source") or "") for row in selected}
    protected_ids = _representative_source_row_ids(selected, ("code", "register", "doc", "pdf"))
    for source_type in ("code", "register", "doc", "pdf"):
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
            replace_index = _diverse_replacement_index(selected, protected_ids)
            selected[replace_index] = candidate
        selected_ids = {row.get("id") for row in selected}
        protected_ids.add(candidate.get("id"))
        selected_sources.add(source_type)
    if not any("provider-vector" in row.get("retrieval_sources", []) for row in selected):
        candidate = next(
            (
                row
                for row in rows
                if "provider-vector" in row.get("retrieval_sources", [])
                and row.get("id") not in selected_ids
            ),
            None,
        )
        if candidate is not None:
            if len(selected) < limit:
                selected.append(candidate)
            else:
                replace_index = _diverse_replacement_index(selected, protected_ids)
                selected[replace_index] = candidate
            protected_ids.add(candidate.get("id"))
    return selected


def _representative_source_row_ids(
    rows: List[Dict[str, Any]],
    source_types: Iterable[str],
) -> set[object]:
    protected: set[object] = set()
    for source_type in source_types:
        representative = next(
            (
                row
                for row in rows
                if str(row.get("source_type") or row.get("source") or "") == source_type
            ),
            None,
        )
        if representative is not None:
            protected.add(representative.get("id"))
    return protected


def _diverse_replacement_index(rows: List[Dict[str, Any]], protected_ids: set[object]) -> int:
    source_counts: Dict[str, int] = {}
    for row in rows:
        source_type = str(row.get("source_type") or row.get("source") or "")
        source_counts[source_type] = source_counts.get(source_type, 0) + 1
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].get("id") in protected_ids:
            continue
        source_type = str(rows[index].get("source_type") or rows[index].get("source") or "")
        if source_counts.get(source_type, 0) > 1:
            return index
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].get("id") not in protected_ids:
            return index
    return len(rows) - 1


def _json_ready(row: Dict[str, object]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if value is not None
    }


def _edge_with_weight(edge: Dict[str, object]) -> Dict[str, Any]:
    result = dict(edge)
    result["weight"] = float(edge.get("weight") or edge.get("confidence") or 0)
    return result


def _graph_edge_payload(edge: Mapping[str, object], compact: bool = False) -> Dict[str, Any]:
    result = _edge_with_weight(dict(edge))
    if not compact:
        return result
    attr = result.get("attr")
    if isinstance(attr, Mapping):
        compact_attr: Dict[str, Any] = {}
        for key in (
            "provider",
            "providers",
            "model",
            "models",
            "job_id",
            "job_ids",
            "dispatch",
            "callback_candidate_count",
            "callback_ambiguous",
            "call_kind",
            "original_relation",
            "evidence",
        ):
            value = attr.get(key)
            if value not in ("", None, [], {}):
                compact_attr[key] = value
        sources = _compact_graph_source_records(attr.get("source", attr.get("sources")), limit=2)
        if sources:
            compact_attr["source"] = sources
        result["attr"] = compact_attr
    return result


def _compact_graph_source_records(value: object, limit: int = 4) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    records: List[Dict[str, Any]] = []
    seen_corpora: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        record = {
            key: item.get(key)
            for key in ("corpus_id", "repo", "path", "line_start", "line_end", "page", "provider", "model", "job_id")
            if item.get(key) not in ("", None, [], {})
        }
        if record:
            corpus_key = str(record.get("corpus_id") or record.get("repo") or "")
            if corpus_key and corpus_key in seen_corpora and len(records) >= limit:
                continue
            records.append(record)
            if corpus_key:
                seen_corpora.add(corpus_key)
        if len(records) >= limit and len(seen_corpora) >= min(limit, 2):
            break
    return records[:limit]


def _compact_graph_attr(attr: Mapping[str, Any]) -> Dict[str, Any]:
    compact = dict(attr)
    sources = _compact_graph_source_records(compact.get("source"))
    if sources:
        page = compact.get("page")
        if page not in ("", None):
            sources = [{**source, **({} if source.get("page") not in ("", None) else {"page": page})} for source in sources]
        compact["source"] = sources
    elif "source" in compact:
        compact.pop("source", None)
    raw_implementations = compact.get("raw_implementations")
    if isinstance(raw_implementations, list):
        compact["raw_implementation_count"] = len(raw_implementations)
        concept_implementations = _compact_concept_implementations(raw_implementations)
        compact["concept_implementation_count"] = len(concept_implementations)
        compact["concept_implementations"] = concept_implementations
        compact.pop("raw_implementations", None)
    for key in (
        "fields",
        "resolver_wrappers",
        "ip_versions",
        "inputs",
        "outputs",
        "constraints",
        "providers",
        "models",
        "job_ids",
        "resolver_profile_ids",
        "raw_function_names",
    ):
        value = compact.get(key)
        if isinstance(value, list):
            compact[f"{key}_count"] = len(value)
            compact[key] = value[:12]
        if compact.get(key) in (None, "", [], {}):
            compact.pop(key, None)
            compact.pop(f"{key}_count", None)
    return compact


def _compact_concept_implementations(value: object, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    records: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        function_name = str(
            item.get("function_name") or item.get("raw_function_name") or item.get("name") or ""
        ).strip()
        path = str(item.get("path") or "").strip()
        line_start = item.get("line_start")
        key = (function_name, path, "")
        if not function_name or key in seen:
            continue
        record = {
            field: item.get(field)
            for field in (
                "function_name",
                "raw_function_name",
                "path",
                "line_start",
                "line_end",
                "ip_block",
                "ip",
                "ip_version",
                "corpus_id",
                "repo",
            )
            if item.get(field) not in ("", None, [], {})
        }
        if not record.get("function_name"):
            record["function_name"] = function_name
        record.pop("raw_function_name", None)
        records.append(record)
        seen.add(key)
        if limit is not None and len(records) >= limit:
            break
    return records if limit is None else records[:limit]


def _node_with_kind(node_id: str) -> Dict[str, Any]:
    return {"id": node_id, "kind": _entity_type_for_symbol(node_id), "weight": 1}


def _product_fallback_node(node_id: str) -> Optional[Dict[str, Any]]:
    node = _node_with_kind(node_id)
    if node["kind"] in {"function", "register", "doc"}:
        return node
    return None


def _graph_node_payload(node: Mapping[str, Any], compact: bool = False) -> Dict[str, Any]:
    node_id = str(node["id"])
    payload = {**_node_with_kind(node_id), **dict(node)}
    payload["id"] = node_id
    payload["kind"] = str(node.get("kind") or payload["kind"])
    payload["weight"] = node.get("weight", 1)
    if compact:
        attr = dict(payload.get("attr") if isinstance(payload.get("attr"), Mapping) else {})
        payload["attr"] = _compact_graph_attr(attr)
    return payload


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
        con = sqlite3.connect(str(db_path), timeout=5.0)
        con.execute("pragma query_only = on")
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
    query_parser.add_argument("--compact-graph", action="store_true")

    graph_parser = subparsers.add_parser("graph")
    graph_parser.add_argument("--db", default=str(DEFAULT_DB))
    graph_parser.add_argument("--symbol")
    graph_parser.add_argument("--hops", type=int)
    graph_parser.add_argument("--limit", type=int)
    graph_parser.add_argument("--all", action="store_true")
    graph_parser.add_argument("--function-view", choices=["concept", "implementation"], default="concept")
    graph_parser.add_argument("--limits-config", "--budget-config", dest="limits_config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

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
        payload = query_evidence(
            Path(args.db),
            args.q,
            ip_block=args.ip_block,
            asic_or_generation=args.asic,
            compact_graph=args.compact_graph,
        )
    elif args.command == "graph":
        limits = load_workbench_limits(Path(args.limits_config))
        hops = args.hops if args.hops is not None else limits.int_value("graph", "default_hops", minimum=1)
        edge_limit = args.limit if args.limit is not None else limits.int_value("graph", "edge_budget", minimum=1)
        payload = (
            expand_query_graph(Path(args.db), args.symbol, hops=hops or 1, function_view=args.function_view)
            if args.symbol
            else global_graph(Path(args.db), limit=edge_limit, all_edges=args.all, function_view=args.function_view)
        )
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
