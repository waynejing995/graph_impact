"""Command line entry points for ASIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from .acceptance import DEFAULT_ACCEPTANCE_QUERIES, run_acceptance_queries
from .limits import DEFAULT_WORKBENCH_LIMITS_PATH, load_workbench_limits
from .performance_smoke import run_fixture_performance_smoke
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
    index.add_argument("--config", required=True)
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

    corpus_add = subcommands.add_parser("corpus-add", help="Add a corpus entry to the ASIP SQLite store")
    corpus_add.add_argument("--db", required=True)
    corpus_add.add_argument("--id", required=True)
    corpus_add.add_argument("--repo", default="local")
    corpus_add.add_argument("--source-root", required=True)
    corpus_add.add_argument("--include", action="append", default=[])
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
            print(json.dumps(expand_query_graph(Path(args.db), args.seed, hops=hops or 1), indent=2))
        else:
            print(
                json.dumps(
                    global_graph(
                        Path(args.db),
                        limit=edge_limit,
                        include_evidence_derived=args.include_evidence_derived,
                        evidence_row_cap=evidence_row_cap,
                        all_edges=args.all,
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
