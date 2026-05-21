"""Command line entry points for ASIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from .acceptance import DEFAULT_ACCEPTANCE_QUERIES, run_acceptance_queries, run_provider_gate
from .closure_gates import run_git_gate, run_residual_acceptance_gate
from .completion_gate import run_completion_gate
from .limits import DEFAULT_WORKBENCH_LIMITS_PATH, load_workbench_limits
from .openai_compatible_smoke import run_openai_compatible_live_smoke
from .performance_smoke import run_fixture_performance_smoke
from .semantic_quality import run_semantic_quality_eval
from .semantic_edges import run_full_corpus_generation, run_generation
from .workbench import (
    add_corpus,
    add_resolver_profile,
    backfill_provider_embeddings,
    expand_query_graph,
    explain_entity,
    generate_doc_nodes_batch,
    generate_semantic_edges_batch,
    generate_semantic_edges_for_query,
    get_evidence_detail,
    get_job,
    global_graph,
    index_configured_corpora,
    index_registered_corpora,
    list_indexed_corpora,
    list_jobs,
    list_resolver_profiles,
    load_provider_settings,
    query_evidence,
    rebuild_deterministic_graph,
    save_provider_settings,
    supersede_stale_jobs,
    validate_resolver_profile,
)


def parse_source_roots(items: Optional[List[str]]) -> Dict[str, Path]:
    roots: Dict[str, Path] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"source root must use corpus_id=path: {item}")
        corpus_id, path = item.split("=", 1)
        if not corpus_id or not path:
            raise ValueError(f"source root must use corpus_id=path: {item}")
        roots[corpus_id] = Path(path)
    return roots


def select_acceptance_queries(query_ids: Optional[List[str]]) -> Optional[List[Dict[str, object]]]:
    if not query_ids:
        return None
    wanted = [item.strip().upper() for item in query_ids if item.strip()]
    query_by_id = {str(query["id"]).upper(): query for query in DEFAULT_ACCEPTANCE_QUERIES}
    missing = [query_id for query_id in wanted if query_id not in query_by_id]
    if missing:
        raise ValueError(f"unknown acceptance query id(s): {', '.join(missing)}")
    return [query_by_id[query_id] for query_id in wanted]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="asip")
    subcommands = parser.add_subparsers(dest="command", required=True)

    edges = subcommands.add_parser("edges", help="Generate and verify semantic edges")
    edges.add_argument("--config", required=True)
    edges.add_argument("--source-root")
    edges.add_argument("--output-json", required=True)
    edges.add_argument("--output-md", required=True)
    edges.add_argument("--min-pass", type=int, default=6)

    edges_full = subcommands.add_parser("edges-full", help="Generate and verify semantic edges from full corpora")
    edges_full.add_argument("--config", required=True)
    edges_full.add_argument(
        "--source-root",
        action="append",
        default=[],
        help="Override corpus source root as corpus_id=/path/to/repo. May be passed more than once.",
    )
    edges_full.add_argument("--output-json", required=True)
    edges_full.add_argument("--output-md", required=True)
    edges_full.add_argument("--min-pass", type=int, default=6)
    edges_full.add_argument("--batch-size", type=int)
    edges_full.add_argument("--limits-config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    index = subcommands.add_parser("index", help="Index configured raw corpora into the ASIP SQLite store")
    index.add_argument("--config")
    index.add_argument("--db", required=True)
    index.add_argument("--corpus-id", action="append", default=[])
    index.add_argument("--resolver-profile-id", action="append", default=[])
    index.add_argument(
        "--source-root",
        action="append",
        default=[],
        help="Override configured corpus source root as corpus_id=/path/to/repo. May be passed more than once.",
    )

    query = subcommands.add_parser("query", help="Query the ASIP SQLite evidence store")
    query.add_argument("--db", required=True)
    query.add_argument("--q", required=True)
    query.add_argument("--ip-block", default="")
    query.add_argument("--asic", default="")
    query.add_argument("--source-type", action="append", default=[])
    query.add_argument("--limit", type=int)
    query.add_argument("--function-view", choices=["concept", "implementation"], default="concept")
    query.add_argument("--compact-graph", action="store_true", help="Return compact graph metadata for UI rendering")
    query.add_argument("--limits-config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    semantic_edges = subcommands.add_parser("semantic-edges", help="Generate semantic edges from indexed evidence")
    semantic_edges.add_argument("--db", required=True)
    semantic_edges.add_argument("--q", required=True)
    semantic_edges.add_argument("--limit", type=int)
    semantic_edges.add_argument("--limits-config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    semantic_edges_batch = subcommands.add_parser(
        "semantic-edges-batch",
        help="Generate semantic edges from indexed corpus candidates",
    )
    semantic_edges_batch.add_argument("--db", required=True)
    semantic_edges_batch.add_argument("--limit", type=int)
    semantic_edges_batch.add_argument("--batch-size", type=int)
    semantic_edges_batch.add_argument("--include-evidence-derived", action="store_true")
    semantic_edges_batch.add_argument("--evidence-row-cap", type=int)
    semantic_edges_batch.add_argument("--limits-config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    doc_nodes_batch = subcommands.add_parser(
        "doc-nodes-batch",
        help="Generate BoxMatrix-style document graph nodes with the configured LLM provider",
    )
    doc_nodes_batch.add_argument("--db", required=True)
    doc_nodes_batch.add_argument("--limit", type=int)
    doc_nodes_batch.add_argument("--batch-size", type=int)
    doc_nodes_batch.add_argument("--limits-config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    graph_rebuild = subcommands.add_parser(
        "graph-rebuild",
        help="Rebuild Stage 1 deterministic graph edges from registered corpora",
    )
    graph_rebuild.add_argument("--db", required=True)
    graph_rebuild.add_argument("--corpus-id", action="append")
    graph_rebuild.add_argument("--resolver-profile-id", action="append", default=[])

    performance_smoke = subcommands.add_parser(
        "performance-smoke",
        help="Rebuild a small fixture twice from empty SQLite DBs and time live queries",
    )
    performance_smoke.add_argument("--db", required=True)
    performance_smoke.add_argument("--source-root", required=True)
    performance_smoke.add_argument("--query", action="append", default=[])
    performance_smoke.add_argument("--corpus-id", default="fixture-performance")
    performance_smoke.add_argument("--limit", type=int, default=8)
    performance_smoke.add_argument("--max-query-seconds", type=float, default=1.0)
    performance_smoke.add_argument("--output-json")

    evidence_detail = subcommands.add_parser("evidence-detail", help="Read a single evidence row by id")
    evidence_detail.add_argument("--db", required=True)
    evidence_detail.add_argument("--id", type=int, required=True)

    entity_explain = subcommands.add_parser("entity-explain", help="Explain an entity with evidence and graph context")
    entity_explain.add_argument("--db", required=True)
    entity_explain.add_argument("--symbol", required=True)

    graph = subcommands.add_parser("graph", help="Expand a weighted relation graph from the ASIP SQLite store")
    graph.add_argument("--db", required=True)
    graph.add_argument("--seed")
    graph.add_argument("--hops", type=int)
    graph.add_argument("--limit", type=int)
    graph.add_argument("--all", action="store_true", help="Return the full global graph without the configured edge budget")
    graph.add_argument("--include-evidence-derived", action="store_true")
    graph.add_argument("--evidence-row-cap", type=int)
    graph.add_argument("--function-view", choices=["concept", "implementation"], default="concept")
    graph.add_argument("--compact", action="store_true", help="Return compact global graph metadata for UI rendering")
    graph.add_argument("--limits-config", "--budget-config", dest="limits_config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    acceptance = subcommands.add_parser("acceptance", help="Run ASIP MVP acceptance queries against a SQLite store")
    acceptance.add_argument("--db", required=True)
    acceptance.add_argument("--output-json")
    acceptance.add_argument("--output-md")
    acceptance.add_argument("--surface", action="append", default=["CLI"])
    acceptance.add_argument("--query-id", action="append", default=[])
    acceptance.add_argument("--full", action="store_true", help="Print the full acceptance payload instead of only summary")

    corpora = subcommands.add_parser("corpora", help="List indexed corpora from the ASIP SQLite store")
    corpora.add_argument("--db", required=True)
    corpora.add_argument("--config")

    jobs = subcommands.add_parser("jobs", help="List or inspect durable ASIP jobs")
    jobs.add_argument("--db", required=True)
    jobs.add_argument("--id", type=int)
    jobs.add_argument("--limit", type=int, default=50)
    jobs.add_argument("--kind", default="index")
    jobs.add_argument("--supersede-stale-before-id", type=int)

    corpus_add = subcommands.add_parser("corpus-add", help="Add a corpus entry to the ASIP SQLite store")
    corpus_add.add_argument("--db", required=True)
    corpus_add.add_argument("--id", required=True)
    corpus_add.add_argument("--repo", default="local")
    corpus_add.add_argument("--source-root", required=True)
    corpus_add.add_argument("--include", action="append", default=[])
    corpus_add.add_argument(
        "--subfolder",
        action="append",
        default=[],
        help="Add a scan subfolder as relative/path:glob,glob. May be passed more than once.",
    )
    corpus_add.add_argument("--type", default="code")

    provider_save = subcommands.add_parser("provider-save", help="Persist provider settings JSON")
    provider_save.add_argument("--db", required=True)
    provider_save.add_argument("--settings-json", required=True)

    provider_show = subcommands.add_parser("provider-show", help="Show persisted provider settings JSON")
    provider_show.add_argument("--db", required=True)

    provider_embeddings = subcommands.add_parser(
        "provider-embeddings",
        help="Backfill provider embeddings for existing indexed chunks using current settings",
    )
    provider_embeddings.add_argument("--db", required=True)
    provider_embeddings.add_argument("--limit", type=int)
    provider_embeddings.add_argument("--batch-size", type=int)
    provider_embeddings.add_argument("--limits-config", default=str(DEFAULT_WORKBENCH_LIMITS_PATH))

    provider_gate = subcommands.add_parser(
        "provider-gate",
        help="Run fast provider provenance and live reachability checks",
    )
    provider_gate.add_argument("--db", required=True)
    provider_gate.add_argument("--output-json")
    provider_gate.add_argument("--full", action="store_true", help="Print the full provider-gate payload")

    openai_compatible_smoke = subcommands.add_parser(
        "openai-compatible-smoke",
        help="Run live OpenAI-compatible embedding and chat endpoint smoke checks",
    )
    openai_compatible_smoke.add_argument("--base-url", required=True)
    openai_compatible_smoke.add_argument("--embedding-model", required=True)
    openai_compatible_smoke.add_argument("--chat-model", required=True)
    openai_compatible_smoke.add_argument("--embedding-api-path", default="/v1/embeddings")
    openai_compatible_smoke.add_argument("--chat-api-path", default="/v1/chat/completions")
    openai_compatible_smoke.add_argument("--api-key-env", default="")
    openai_compatible_smoke.add_argument("--require-credentialed", action="store_true")
    openai_compatible_smoke.add_argument("--timeout-seconds", type=int, default=60)
    openai_compatible_smoke.add_argument("--output-json")
    openai_compatible_smoke.add_argument("--full", action="store_true", help="Print the full smoke payload")

    semantic_quality = subcommands.add_parser(
        "semantic-quality",
        help="Run labeled semantic retrieval quality checks against a SQLite store",
    )
    semantic_quality.add_argument("--db", required=True)
    semantic_quality.add_argument("--eval-set", required=True)
    semantic_quality.add_argument("--output-json")
    semantic_quality.add_argument("--output-md")
    semantic_quality.add_argument("--full", action="store_true", help="Print the full semantic-quality payload")

    completion_gate = subcommands.add_parser(
        "completion-gate",
        help="Aggregate current ASIP final-goal artifacts into one pass/blocked gate",
    )
    completion_gate.add_argument("--db", required=True)
    completion_gate.add_argument("--acceptance-json")
    completion_gate.add_argument("--web-acceptance-json")
    completion_gate.add_argument("--provider-json")
    completion_gate.add_argument("--runtime-semantic-json")
    completion_gate.add_argument("--semantic-quality-json")
    completion_gate.add_argument("--callback-audit-json")
    completion_gate.add_argument("--browser-json")
    completion_gate.add_argument("--in-app-browser-json")
    completion_gate.add_argument("--no-server-json")
    completion_gate.add_argument("--performance-json")
    completion_gate.add_argument("--hosted-openai-json")
    completion_gate.add_argument("--residual-acceptance-json")
    completion_gate.add_argument("--git-gate-json")
    completion_gate.add_argument("--output-json")
    completion_gate.add_argument("--output-md")
    completion_gate.add_argument(
        "--full-integrity-check",
        action="store_true",
        help="Use SQLite integrity_check instead of the faster quick_check",
    )
    completion_gate.add_argument("--full", action="store_true", help="Print the full completion-gate payload")

    residual_gate = subcommands.add_parser(
        "residual-gate",
        help="Record whether G13 residual boundaries have explicit user acceptance and an accepted residual document status",
    )
    residual_gate.add_argument("--residual-doc", default="docs/gaps/2026-05-16-g13-mvp-boundary-deferrals.md")
    residual_gate.add_argument("--accepted", action="store_true")
    residual_gate.add_argument("--accepted-residual", action="append", default=[])
    residual_gate.add_argument("--output-json")
    residual_gate.add_argument(
        "--require-pass",
        action="store_true",
        help="Exit non-zero when the residual gate is blocked",
    )
    residual_gate.add_argument("--full", action="store_true", help="Print the full residual-gate payload")

    git_gate = subcommands.add_parser("git-gate", help="Record final diff, commit, and push gate state")
    git_gate.add_argument("--repo-root", default=".")
    git_gate.add_argument("--output-json")
    git_gate.add_argument("--full", action="store_true", help="Print the full git-gate payload")

    resolver_list = subcommands.add_parser("resolver-list", help="List resolver profiles from backend state")
    resolver_list.add_argument("--db", required=True)

    resolver_add = subcommands.add_parser("resolver-add", help="Add a resolver profile to backend state")
    resolver_add.add_argument("--db", required=True)
    resolver_add.add_argument("--id", required=True)
    resolver_add.add_argument("--language", required=True)
    resolver_add.add_argument("--wrapper", action="append", default=[])
    resolver_add.add_argument("--strategy", default="macro")
    resolver_add.add_argument("--path", default="")
    resolver_add.add_argument("--disabled", action="store_true")

    resolver_validate = subcommands.add_parser("resolver-validate", help="Validate a resolver profile against source text")
    resolver_validate.add_argument("--db", required=True)
    resolver_validate.add_argument("--id", required=True)
    resolver_validate.add_argument("--source", required=True)

    args = parser.parse_args(argv)
    if args.command == "edges":
        result = run_generation(
            config_path=Path(args.config),
            source_root=Path(args.source_root) if args.source_root else None,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            min_pass=args.min_pass,
        )
        print(json.dumps(result["summary"], indent=2))
        return 0
    if args.command == "edges-full":
        limits = load_workbench_limits(Path(args.limits_config))
        full_corpus_batch_size = (
            args.batch_size
            if args.batch_size is not None
            else limits.int_value("semantic", "full_corpus_batch_size", minimum=1)
        )
        result = run_full_corpus_generation(
            config_path=Path(args.config),
            source_roots=parse_source_roots(args.source_root),
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            min_pass=args.min_pass,
            batch_size=full_corpus_batch_size,
        )
        print(json.dumps(result["summary"], indent=2))
        return 0
    if args.command == "index":
        if args.corpus_id:
            print(
                json.dumps(
                    index_registered_corpora(
                        Path(args.db),
                        corpus_ids=args.corpus_id,
                        resolver_profile_ids=args.resolver_profile_id or None,
                    ),
                    indent=2,
                )
            )
        else:
            if not args.config:
                parser.error("--config is required unless --corpus-id is provided")
            print(
                json.dumps(
                    index_configured_corpora(
                        Path(args.config),
                        Path(args.db),
                        source_roots=parse_source_roots(args.source_root),
                        resolver_profile_ids=args.resolver_profile_id or None,
                    ),
                    indent=2,
                )
            )
        return 0
    if args.command == "query":
        limits = load_workbench_limits(Path(args.limits_config))
        query_limit = args.limit if args.limit is not None else limits.int_value("retrieval", "result_limit", minimum=1)
        print(
            json.dumps(
                query_evidence(
                    Path(args.db),
                    args.q,
                    limit=query_limit,
                    ip_block=args.ip_block,
                    asic_or_generation=args.asic,
                    source_types=args.source_type,
                    function_view=args.function_view,
                    compact_graph=args.compact_graph,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "semantic-edges":
        limits = load_workbench_limits(Path(args.limits_config))
        query_limit = args.limit if args.limit is not None else limits.int_value("semantic", "query_limit", minimum=1)
        print(json.dumps(generate_semantic_edges_for_query(Path(args.db), args.q, limit=query_limit), indent=2))
        return 0
    if args.command == "semantic-edges-batch":
        limits = load_workbench_limits(Path(args.limits_config))
        batch_limit = args.limit if args.limit is not None else limits.int_value("semantic", "batch_candidate_limit", minimum=1)
        batch_size = args.batch_size if args.batch_size is not None else limits.int_value("semantic", "batch_size", minimum=1)
        evidence_row_cap = args.evidence_row_cap if args.evidence_row_cap is not None else limits.int_value("graph", "evidence_row_cap", minimum=0)
        print(
            json.dumps(
                generate_semantic_edges_batch(
                    Path(args.db),
                    limit=batch_limit,
                    batch_size=batch_size,
                    include_evidence_derived=args.include_evidence_derived,
                    evidence_row_cap=evidence_row_cap,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "doc-nodes-batch":
        limits = load_workbench_limits(Path(args.limits_config))
        batch_limit = args.limit if args.limit is not None else limits.int_value("semantic", "batch_candidate_limit", minimum=1)
        batch_size = args.batch_size if args.batch_size is not None else limits.int_value("semantic", "batch_size", minimum=1)
        print(
            json.dumps(
                generate_doc_nodes_batch(
                    Path(args.db),
                    limit=batch_limit,
                    batch_size=batch_size,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "graph-rebuild":
        print(
            json.dumps(
                rebuild_deterministic_graph(
                    Path(args.db),
                    corpus_ids=args.corpus_id,
                    resolver_profile_ids=args.resolver_profile_id or None,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "performance-smoke":
        result = run_fixture_performance_smoke(
            Path(args.db),
            source_root=Path(args.source_root),
            queries=args.query or None,
            corpus_id=args.corpus_id,
            query_limit=args.limit,
            max_query_seconds=args.max_query_seconds,
        )
        if args.output_json:
            Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "evidence-detail":
        print(json.dumps(get_evidence_detail(Path(args.db), args.id), indent=2))
        return 0
    if args.command == "entity-explain":
        print(json.dumps(explain_entity(Path(args.db), args.symbol), indent=2))
        return 0
    if args.command == "graph":
        limits = load_workbench_limits(Path(args.limits_config))
        hops = args.hops if args.hops is not None else limits.int_value("graph", "default_hops", minimum=1)
        edge_limit = args.limit if args.limit is not None else limits.int_value("graph", "edge_budget", minimum=1)
        evidence_row_cap = args.evidence_row_cap if args.evidence_row_cap is not None else limits.int_value("graph", "evidence_row_cap", minimum=0)
        if args.seed:
            print(
                json.dumps(
                    expand_query_graph(Path(args.db), args.seed, hops=hops or 1, function_view=args.function_view),
                    indent=2,
                )
            )
        else:
            print(
                json.dumps(
                    global_graph(
                        Path(args.db),
                        limit=edge_limit,
                        include_evidence_derived=args.include_evidence_derived,
                        evidence_row_cap=evidence_row_cap,
                        all_edges=args.all,
                        function_view=args.function_view,
                        compact=args.compact,
                    ),
                    indent=2,
                )
            )
        return 0
    if args.command == "acceptance":
        try:
            selected_queries = select_acceptance_queries(args.query_id)
        except ValueError as exc:
            parser.error(str(exc))
        result = run_acceptance_queries(
            Path(args.db),
            output_json=Path(args.output_json) if args.output_json else None,
            output_md=Path(args.output_md) if args.output_md else None,
            queries=selected_queries,
            surfaces_checked=args.surface,
        )
        print(json.dumps(result if args.full else result["summary"], indent=2))
        return 0
    if args.command == "corpora":
        print(
            json.dumps(
                {"corpora": list_indexed_corpora(Path(args.db), Path(args.config) if args.config else None)},
                indent=2,
            )
        )
        return 0
    if args.command == "jobs":
        if args.supersede_stale_before_id is not None:
            print(
                json.dumps(
                    supersede_stale_jobs(
                        Path(args.db),
                        before_job_id=args.supersede_stale_before_id,
                        kind=args.kind,
                    ),
                    indent=2,
                )
            )
            return 0
        if args.id is not None:
            print(json.dumps(get_job(Path(args.db), args.id), indent=2))
        else:
            print(json.dumps({"jobs": list_jobs(Path(args.db), limit=args.limit)}, indent=2))
        return 0
    if args.command == "corpus-add":
        print(
            json.dumps(
                add_corpus(
                    Path(args.db),
                    corpus_id=args.id,
                    repo=args.repo,
                    source_root=args.source_root,
                    include=args.include or ["**/*"],
                    corpus_type=args.type,
                    subfolders=args.subfolder,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "provider-save":
        print(json.dumps(save_provider_settings(Path(args.db), json.loads(args.settings_json)), indent=2))
        return 0
    if args.command == "provider-show":
        print(json.dumps(load_provider_settings(Path(args.db)), indent=2))
        return 0
    if args.command == "provider-embeddings":
        limits = load_workbench_limits(Path(args.limits_config))
        embedding_limit = args.limit if args.limit is not None else limits.int_value("embedding", "backfill_limit", minimum=0)
        embedding_batch_size = args.batch_size if args.batch_size is not None else limits.int_value("embedding", "batch_size", minimum=1)
        print(
            json.dumps(
                backfill_provider_embeddings(Path(args.db), limit=embedding_limit, batch_size=embedding_batch_size),
                indent=2,
            )
        )
        return 0
    if args.command == "provider-gate":
        result = run_provider_gate(
            Path(args.db),
            output_json=Path(args.output_json) if args.output_json else None,
        )
        print(json.dumps(result if args.full else result["summary"], indent=2))
        return 0
    if args.command == "openai-compatible-smoke":
        result = run_openai_compatible_live_smoke(
            base_url=args.base_url,
            embedding_model=args.embedding_model,
            chat_model=args.chat_model,
            embedding_api_path=args.embedding_api_path,
            chat_api_path=args.chat_api_path,
            api_key_env=args.api_key_env,
            require_credentialed=args.require_credentialed,
            timeout_seconds=args.timeout_seconds,
            output_json=Path(args.output_json) if args.output_json else None,
        )
        print(json.dumps(result if args.full else result["summary"], indent=2))
        return 0
    if args.command == "semantic-quality":
        result = run_semantic_quality_eval(
            Path(args.db),
            Path(args.eval_set),
            output_json=Path(args.output_json) if args.output_json else None,
            output_md=Path(args.output_md) if args.output_md else None,
        )
        print(json.dumps(result if args.full else result["summary"], indent=2))
        return 0
    if args.command == "completion-gate":
        result = run_completion_gate(
            Path(args.db),
            acceptance_json=Path(args.acceptance_json) if args.acceptance_json else None,
            web_acceptance_json=Path(args.web_acceptance_json) if args.web_acceptance_json else None,
            provider_json=Path(args.provider_json) if args.provider_json else None,
            runtime_semantic_json=Path(args.runtime_semantic_json) if args.runtime_semantic_json else None,
            semantic_quality_json=Path(args.semantic_quality_json) if args.semantic_quality_json else None,
            callback_audit_json=Path(args.callback_audit_json) if args.callback_audit_json else None,
            browser_json=Path(args.browser_json) if args.browser_json else None,
            in_app_browser_json=Path(args.in_app_browser_json) if args.in_app_browser_json else None,
            no_server_json=Path(args.no_server_json) if args.no_server_json else None,
            performance_json=Path(args.performance_json) if args.performance_json else None,
            hosted_openai_json=Path(args.hosted_openai_json) if args.hosted_openai_json else None,
            residual_acceptance_json=Path(args.residual_acceptance_json) if args.residual_acceptance_json else None,
            git_gate_json=Path(args.git_gate_json) if args.git_gate_json else None,
            output_json=Path(args.output_json) if args.output_json else None,
            output_md=Path(args.output_md) if args.output_md else None,
            full_integrity_check=args.full_integrity_check,
        )
        print(json.dumps(result if args.full else result["summary"], indent=2))
        return 0
    if args.command == "residual-gate":
        result = run_residual_acceptance_gate(
            Path(args.residual_doc),
            accepted=args.accepted,
            accepted_residuals=args.accepted_residual,
            output_json=Path(args.output_json) if args.output_json else None,
        )
        print(json.dumps(result if args.full else {"gate_status": result["gate_status"]}, indent=2))
        if args.require_pass and result["gate_status"] != "pass":
            return 2
        return 0
    if args.command == "git-gate":
        result = run_git_gate(
            Path(args.repo_root),
            output_json=Path(args.output_json) if args.output_json else None,
        )
        print(json.dumps(result if args.full else {"gate_status": result["gate_status"]}, indent=2))
        return 0
    if args.command == "resolver-list":
        print(json.dumps({"profiles": list_resolver_profiles(Path(args.db))}, indent=2))
        return 0
    if args.command == "resolver-add":
        print(
            json.dumps(
                add_resolver_profile(
                    Path(args.db),
                    profile_id=args.id,
                    language=args.language,
                    wrappers=args.wrapper,
                    strategy=args.strategy,
                    path=args.path or f"configs/resolvers/{args.id}.yaml",
                    enabled=not args.disabled,
                ),
                indent=2,
            )
        )
        return 0
    if args.command == "resolver-validate":
        print(json.dumps(validate_resolver_profile(Path(args.db), args.id, args.source), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
