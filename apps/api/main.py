"""FastAPI surface for ASIP workbench data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from apps.mcp.tools import (
    acceptance_runs,
    corpora_index,
    corpora_list,
    corpus_add,
    entity_explain,
    evidence_detail,
    graph_rebuild,
    graph_expand,
    job_detail,
    jobs_list,
    provider_settings_save,
    provider_settings_show,
    ollama_models,
    resolver_inspect,
    resolver_profile_add,
    resolver_profile_validate,
    resolver_profiles_list,
    run_acceptance,
    search_evidence,
    semantic_doc_nodes_generate_batch,
    semantic_edges_generate_batch,
    semantic_edges_generate,
)


app = FastAPI(title="ASIP Workbench API")


def _normalize_api_function_view(value: Optional[str]) -> str:
    normalized = (value or "concept").strip().lower()
    if normalized not in {"concept", "implementation"}:
        raise HTTPException(status_code=400, detail="function_view must be concept or implementation")
    return normalized


def _normalize_semantic_mode(value: str) -> str:
    normalized = (value or "query").strip().lower().replace("_", "-")
    aliases = {
        "query": "query",
        "batch": "batch",
        "doc-node": "doc-nodes",
        "doc-nodes": "doc-nodes",
        "docnodes": "doc-nodes",
    }
    if normalized not in aliases:
        raise HTTPException(status_code=400, detail="semantic edge mode must be query, batch, or doc-nodes")
    return aliases[normalized]


class AcceptanceRunRequest(BaseModel):
    query_ids: Optional[List[str]] = None
    surfaces: Optional[List[str]] = None
    db_path: Optional[str] = None


class CorpusRequest(BaseModel):
    id: str
    repo: str = "local"
    source_root: str
    include: List[str] = ["**/*"]
    type: str = "code"
    db_path: Optional[str] = None


class IndexRequest(BaseModel):
    corpus_ids: Optional[List[str]] = None
    resolver_profile_ids: Optional[List[str]] = None
    resolverProfileIds: Optional[List[str]] = None
    db_path: Optional[str] = None


class GraphRebuildRequest(BaseModel):
    corpus_ids: Optional[List[str]] = None
    resolver_profile_ids: Optional[List[str]] = None
    resolverProfileIds: Optional[List[str]] = None
    db_path: Optional[str] = None


class SemanticEdgesRequest(BaseModel):
    q: str = ""
    db_path: Optional[str] = None
    limit: Optional[int] = None
    mode: str = "query"
    batch_size: Optional[int] = None


class ProviderSettingsRequest(BaseModel):
    settings: Dict[str, Any]
    db_path: Optional[str] = None


class ResolverProfileRequest(BaseModel):
    id: str
    language: str
    wrappers: List[str]
    strategy: str = "macro"
    path: str = ""
    enabled: bool = True
    db_path: Optional[str] = None


class ResolverValidateRequest(BaseModel):
    source: str
    db_path: Optional[str] = None


@app.get("/query")
def query(
    q: str,
    db_path: Optional[str] = None,
    ip_block: str = "",
    asic: str = "",
    asic_or_generation: str = "",
    function_view: str = "concept",
    functionView: Optional[str] = None,
    compact_graph: bool = False,
    compactGraph: Optional[bool] = None,
):
    selected_function_view = _normalize_api_function_view(functionView or function_view)
    return search_evidence(
        q,
        db_path=db_path,
        ip_block=ip_block,
        asic_or_generation=asic_or_generation or asic,
        function_view=selected_function_view,
        compact_graph=compactGraph if compactGraph is not None else compact_graph,
    )


@app.get("/graph")
def graph(
    query_id: str,
    db_path: Optional[str] = None,
    function_view: str = "concept",
    functionView: Optional[str] = None,
):
    selected_function_view = _normalize_api_function_view(functionView or function_view)
    return graph_expand(query_id, db_path=db_path, function_view=selected_function_view)


@app.post("/semantic-edges")
def semantic_edges(request: SemanticEdgesRequest):
    mode = _normalize_semantic_mode(request.mode)
    try:
        if mode == "doc-nodes":
            return semantic_doc_nodes_generate_batch(
                db_path=request.db_path,
                limit=request.limit,
                batch_size=request.batch_size,
            )
        if mode == "batch":
            return semantic_edges_generate_batch(
                db_path=request.db_path,
                limit=request.limit,
                batch_size=request.batch_size,
            )
        return semantic_edges_generate(
            request.q,
            db_path=request.db_path,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/evidence/{evidence_id}")
def evidence(evidence_id: int, db_path: Optional[str] = None):
    try:
        return evidence_detail(evidence_id=evidence_id, db_path=db_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/entities/{symbol}")
def entity(symbol: str, db_path: Optional[str] = None):
    return entity_explain(symbol=symbol, db_path=db_path)


@app.get("/corpora")
def corpora(db_path: Optional[str] = None):
    return corpora_list(db_path=db_path)


@app.post("/corpora")
def create_corpus(request: CorpusRequest):
    return corpus_add(
        db_path=request.db_path,
        corpus_id=request.id,
        repo=request.repo,
        source_root=request.source_root,
        include=request.include,
        corpus_type=request.type,
    )


@app.post("/index")
def index(request: IndexRequest):
    return corpora_index(
        db_path=request.db_path,
        corpus_ids=request.corpus_ids,
        resolver_profile_ids=request.resolver_profile_ids or request.resolverProfileIds,
    )


@app.post("/graph-rebuild")
def rebuild_graph(request: GraphRebuildRequest):
    try:
        return graph_rebuild(
            db_path=request.db_path,
            corpus_ids=request.corpus_ids,
            resolver_profile_ids=request.resolver_profile_ids or request.resolverProfileIds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/jobs")
def jobs(db_path: Optional[str] = None, limit: int = 50):
    return jobs_list(db_path=db_path, limit=limit)


@app.get("/jobs/{job_id}")
def job(job_id: int, db_path: Optional[str] = None):
    try:
        return job_detail(job_id, db_path=db_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc


@app.get("/providers/settings")
def providers_settings(db_path: Optional[str] = None):
    return provider_settings_show(db_path=db_path)


@app.post("/providers/settings")
def save_providers_settings(request: ProviderSettingsRequest):
    return provider_settings_save(request.settings, db_path=request.db_path)


@app.get("/providers/ollama-tags")
def providers_ollama_tags(base_url: str = "http://localhost:11434", timeout_seconds: int = 5):
    return ollama_models(base_url=base_url, timeout_seconds=timeout_seconds)


@app.get("/resolver-profiles")
def resolver_profiles(db_path: Optional[str] = None):
    return resolver_profiles_list(db_path=db_path)


@app.post("/resolver-profiles")
def create_resolver_profile(request: ResolverProfileRequest):
    return resolver_profile_add(
        db_path=request.db_path,
        profile_id=request.id,
        language=request.language,
        wrappers=request.wrappers,
        strategy=request.strategy,
        path=request.path or f"configs/resolvers/{request.id}.yaml",
        enabled=request.enabled,
    )


@app.get("/resolver-profiles/{profile_id}")
def resolver_profile(profile_id: str):
    return resolver_inspect(profile_id)


@app.post("/resolver-profiles/{profile_id}/validate")
def validate_resolver_profile_endpoint(profile_id: str, request: ResolverValidateRequest):
    return resolver_profile_validate(profile_id=profile_id, source=request.source, db_path=request.db_path)


@app.get("/acceptance/runs")
def acceptance():
    return {"runs": acceptance_runs()}


@app.post("/acceptance/run")
def acceptance_run(request: AcceptanceRunRequest):
    try:
        return run_acceptance(
            query_ids=request.query_ids,
            surfaces=request.surfaces or ["API"],
            db_path=request.db_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
