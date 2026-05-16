"""Index generated ASIP QA artifacts into the SQLite evidence store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .storage import AsipStore


def index_full_corpus_run(run_path: Path, db_path: Path) -> Dict[str, int | str]:
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    store = AsipStore.connect(str(db_path))
    store.migrate()
    document_ids: Dict[tuple[str, str], int] = {}
    chunk_count = 0
    edge_count = 0

    for query in payload.get("scan", {}).get("queries", []):
        corpus_id = str(query.get("corpus", "unknown"))
        for snippet in query.get("snippets", []):
            snippet_path = str(snippet["path"])
            key = (corpus_id, snippet_path)
            if key not in document_ids:
                document_ids[key] = store.add_document(
                    corpus_id=corpus_id,
                    source_type=_source_type_for_path(snippet_path),
                    path=snippet_path,
                )
            store.add_chunk(
                document_id=document_ids[key],
                text=str(snippet.get("text", "")),
                line_start=int(snippet.get("line_start", 0)),
                line_end=int(snippet.get("line_end", 0)),
            )
            chunk_count += 1

    for generated_case in payload.get("generated", {}).get("cases", []):
        for edge in generated_case.get("edges", []):
            store.add_edge(
                src=str(edge["src"]),
                dst=str(edge["dst"]),
                relation=str(edge["relation"]),
                confidence=float(edge.get("confidence", 0)),
            )
            edge_count += 1

    return {
        "db_path": str(db_path),
        "documents": len(document_ids),
        "chunks": chunk_count,
        "edges": edge_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asip.index_artifacts")
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--db", required=True)
    args = parser.parse_args(argv)

    print(json.dumps(index_full_corpus_run(Path(args.run_json), Path(args.db)), indent=2))
    return 0


def _source_type_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".md", ".rst", ".txt"}:
        return "doc"
    if suffix == ".pdf":
        return "pdf"
    return "code"


if __name__ == "__main__":
    raise SystemExit(main())
