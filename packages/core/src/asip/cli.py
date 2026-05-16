"""Command line entry points for ASIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from .semantic_edges import run_full_corpus_generation, run_generation


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
    edges_full.add_argument("--batch-size", type=int, default=3)

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
        result = run_full_corpus_generation(
            config_path=Path(args.config),
            source_roots=parse_source_roots(args.source_root),
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            min_pass=args.min_pass,
            batch_size=args.batch_size,
        )
        print(json.dumps(result["summary"], indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
