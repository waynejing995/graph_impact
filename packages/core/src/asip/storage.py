"""SQLite evidence storage and graph expansion utilities."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class AsipStore:
    con: sqlite3.Connection

    @classmethod
    def connect(cls, path: str) -> "AsipStore":
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        return cls(con=con)

    def migrate(self) -> None:
        self.con.executescript(
            """
            create table if not exists corpora (
              id text primary key,
              repo text not null,
              source_root text not null,
              include_json text not null,
              status text not null default 'not_indexed',
              file_count integer not null default 0,
              metadata_json text not null default '{}'
            );

            create table if not exists jobs (
              id integer primary key,
              kind text not null,
              status text not null,
              message text not null default '',
              metadata_json text not null default '{}',
              started_at text not null default current_timestamp,
              finished_at text
            );

            create table if not exists documents (
              id integer primary key,
              corpus_id text not null,
              source_type text not null,
              path text not null
            );

            create table if not exists chunks (
              id integer primary key,
              document_id integer not null references documents(id),
              text text not null,
              line_start integer,
              line_end integer,
              page integer
            );

            create virtual table if not exists chunks_fts using fts5(
              text,
              content='chunks',
              content_rowid='id'
            );

            create table if not exists edges (
              id integer primary key,
              src text not null,
              dst text not null,
              relation text not null,
              confidence real not null
            );

            create table if not exists evidence (
              id integer primary key,
              chunk_id integer not null references chunks(id),
              corpus_id text not null,
              source_type text not null,
              repo text not null,
              path text not null,
              line_start integer,
              line_end integer,
              page integer,
              symbol text not null,
              entity_type text not null,
              ip_block text not null default '',
              asic_or_generation text not null default '',
              access_type text not null,
              confidence real not null,
              snippet text not null,
              resolved_chain text not null,
              query_id text not null default ''
            );

            create table if not exists resolver_profiles (
              id text primary key,
              language text not null,
              wrappers_json text not null,
              strategy text not null,
              path text not null,
              enabled integer not null default 1,
              config_json text not null default '{}'
            );

            create table if not exists provider_settings (
              id text primary key,
              settings_json text not null
            );

            create table if not exists embeddings (
              chunk_id integer primary key references chunks(id),
              provider text not null,
              model text not null,
              vector_json text not null,
              metadata_json text not null default '{}'
            );
            """
        )
        self._ensure_column("chunks", "page", "integer")
        self._ensure_column("jobs", "metadata_json", "text not null default '{}'")
        self._ensure_column("embeddings", "metadata_json", "text not null default '{}'")
        self.con.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.con.execute(f"pragma table_info({table})")}
        if column not in columns:
            self.con.execute(f"alter table {table} add column {column} {definition}")

    def reset_index(self) -> None:
        self.con.executescript(
            """
            delete from evidence;
            delete from embeddings;
            delete from edges;
            delete from chunks_fts;
            delete from chunks;
            delete from documents;
            delete from jobs;
            """
        )
        self.con.commit()

    def start_job(self, kind: str, message: str = "", metadata: Optional[Dict[str, object]] = None) -> int:
        cursor = self.con.execute(
            "insert into jobs(kind, status, message, metadata_json) values (?, 'running', ?, ?)",
            (kind, message, json.dumps(metadata or {})),
        )
        self.con.commit()
        return int(cursor.lastrowid)

    def finish_job(self, job_id: int, status: str, message: str = "") -> None:
        self.con.execute(
            """
            update jobs
            set status = ?, message = ?, finished_at = current_timestamp
            where id = ?
            """,
            (status, message, job_id),
        )
        self.con.commit()

    def get_job(self, job_id: int) -> Dict[str, object]:
        row = self.con.execute(
            "select id, kind, status, message, metadata_json, started_at, finished_at from jobs where id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        result = dict(row)
        result["metadata"] = json.loads(str(result.pop("metadata_json")))
        return result

    def upsert_corpus(
        self,
        corpus_id: str,
        repo: str,
        source_root: str,
        include: Iterable[str],
        status: str = "not_indexed",
        file_count: int = 0,
        metadata: Optional[Dict[str, object]] = None,
    ) -> None:
        self.con.execute(
            """
            insert into corpora(id, repo, source_root, include_json, status, file_count, metadata_json)
            values (?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
              repo=excluded.repo,
              source_root=excluded.source_root,
              include_json=excluded.include_json,
              status=excluded.status,
              file_count=excluded.file_count,
              metadata_json=excluded.metadata_json
            """,
            (
                corpus_id,
                repo,
                source_root,
                json.dumps(list(include)),
                status,
                file_count,
                json.dumps(metadata or {}),
            ),
        )
        self.con.commit()

    def list_corpora(self) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select id, repo, source_root, include_json, status, file_count, metadata_json
            from corpora
            order by id
            """
        )
        corpora = []
        for row in rows:
            corpora.append(
                {
                    "id": row["id"],
                    "repo": row["repo"],
                    "source_root": row["source_root"],
                    "include": json.loads(str(row["include_json"])),
                    "status": row["status"],
                    "file_count": int(row["file_count"]),
                    "metadata": json.loads(str(row["metadata_json"])),
                }
            )
        return corpora

    def delete_index_for_corpora(self, corpus_ids: Iterable[str]) -> None:
        ids = list(dict.fromkeys(corpus_ids))
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        document_rows = self.con.execute(
            f"select id from documents where corpus_id in ({placeholders})",
            tuple(ids),
        ).fetchall()
        document_ids = [int(row["id"]) for row in document_rows]
        if document_ids:
            doc_placeholders = ",".join("?" for _ in document_ids)
            chunk_rows = self.con.execute(
                f"select id from chunks where document_id in ({doc_placeholders})",
                tuple(document_ids),
            ).fetchall()
            chunk_ids = [int(row["id"]) for row in chunk_rows]
            if chunk_ids:
                chunk_placeholders = ",".join("?" for _ in chunk_ids)
                self.con.execute(f"delete from evidence where chunk_id in ({chunk_placeholders})", tuple(chunk_ids))
                self.con.execute(f"delete from embeddings where chunk_id in ({chunk_placeholders})", tuple(chunk_ids))
                self.con.execute(f"delete from chunks_fts where rowid in ({chunk_placeholders})", tuple(chunk_ids))
                self.con.execute(f"delete from chunks where id in ({chunk_placeholders})", tuple(chunk_ids))
            self.con.execute(f"delete from documents where id in ({doc_placeholders})", tuple(document_ids))
        self.con.commit()

    def add_document(self, corpus_id: str, source_type: str, path: str) -> int:
        cursor = self.con.execute(
            "insert into documents(corpus_id, source_type, path) values (?, ?, ?)",
            (corpus_id, source_type, path),
        )
        self.con.commit()
        return int(cursor.lastrowid)

    def add_chunk(self, document_id: int, text: str, line_start: int, line_end: int, page: int | None = None) -> int:
        cursor = self.con.execute(
            "insert into chunks(document_id, text, line_start, line_end, page) values (?, ?, ?, ?, ?)",
            (document_id, text, line_start, line_end, page),
        )
        chunk_id = int(cursor.lastrowid)
        self.con.execute("insert into chunks_fts(rowid, text) values (?, ?)", (chunk_id, text))
        self.con.commit()
        return chunk_id

    def search_text(self, query: str) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select
              chunks.id,
              documents.corpus_id,
              documents.source_type,
              documents.path,
              chunks.line_start,
              chunks.line_end,
              chunks.page,
              chunks.text
            from chunks_fts
            join chunks on chunks.id = chunks_fts.rowid
            join documents on documents.id = chunks.document_id
            where chunks_fts match ?
            order by bm25(chunks_fts)
            """,
            (query,),
        )
        return [dict(row) for row in rows]

    def add_evidence(
        self,
        chunk_id: int,
        corpus_id: str,
        source_type: str,
        repo: str,
        path: str,
        symbol: str,
        entity_type: str,
        access_type: str,
        confidence: float,
        snippet: str,
        resolved_chain: str,
        line_start: int | None = None,
        line_end: int | None = None,
        page: int | None = None,
        ip_block: str = "",
        asic_or_generation: str = "",
        query_id: str = "",
    ) -> int:
        cursor = self.con.execute(
            """
            insert into evidence(
              chunk_id, corpus_id, source_type, repo, path, line_start, line_end, page,
              symbol, entity_type, ip_block, asic_or_generation, access_type,
              confidence, snippet, resolved_chain, query_id
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                corpus_id,
                source_type,
                repo,
                path,
                line_start,
                line_end,
                page,
                symbol,
                entity_type,
                ip_block,
                asic_or_generation,
                access_type,
                confidence,
                snippet,
                resolved_chain,
                query_id,
            ),
        )
        self.con.commit()
        return int(cursor.lastrowid)

    def all_evidence(self) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select
              id, chunk_id, corpus_id, source_type, repo, path, line_start, line_end, page,
              symbol, entity_type, ip_block, asic_or_generation, access_type,
              confidence, snippet, resolved_chain, query_id
            from evidence
            order by confidence desc, id asc
            """
        )
        return [dict(row) for row in rows]

    def evidence_for_chunks(self, chunk_ids: Iterable[int]) -> List[Dict[str, object]]:
        ids = list(dict.fromkeys(int(chunk_id) for chunk_id in chunk_ids))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.con.execute(
            f"""
            select
              id, chunk_id, corpus_id, source_type, repo, path, line_start, line_end, page,
              symbol, entity_type, ip_block, asic_or_generation, access_type,
              confidence, snippet, resolved_chain, query_id
            from evidence
            where chunk_id in ({placeholders})
            order by confidence desc, id asc
            """,
            tuple(ids),
        )
        return [dict(row) for row in rows]

    def add_edge(self, src: str, dst: str, relation: str, confidence: float) -> int:
        cursor = self.con.execute(
            "insert into edges(src, dst, relation, confidence) values (?, ?, ?, ?)",
            (src, dst, relation, confidence),
        )
        self.con.commit()
        return int(cursor.lastrowid)

    def add_embedding(
        self,
        chunk_id: int,
        provider: str,
        model: str,
        vector: List[float],
        metadata: Optional[Dict[str, object]] = None,
    ) -> None:
        self.con.execute(
            """
            insert into embeddings(chunk_id, provider, model, vector_json, metadata_json)
            values (?, ?, ?, ?, ?)
            on conflict(chunk_id) do update set
              provider=excluded.provider,
              model=excluded.model,
              vector_json=excluded.vector_json,
              metadata_json=excluded.metadata_json
            """,
            (chunk_id, provider, model, json.dumps(vector), json.dumps(metadata or {})),
        )
        self.con.commit()

    def upsert_resolver_profile(
        self,
        profile_id: str,
        language: str,
        wrappers: Iterable[str],
        strategy: str,
        path: str,
        enabled: bool = True,
        config: Optional[Dict[str, object]] = None,
    ) -> None:
        self.con.execute(
            """
            insert into resolver_profiles(id, language, wrappers_json, strategy, path, enabled, config_json)
            values (?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
              language=excluded.language,
              wrappers_json=excluded.wrappers_json,
              strategy=excluded.strategy,
              path=excluded.path,
              enabled=excluded.enabled,
              config_json=excluded.config_json
            """,
            (
                profile_id,
                language,
                json.dumps(list(wrappers)),
                strategy,
                path,
                1 if enabled else 0,
                json.dumps(config or {}),
            ),
        )
        self.con.commit()

    def list_resolver_profiles(self) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select id, language, wrappers_json, strategy, path, enabled, config_json
            from resolver_profiles
            order by id
            """
        )
        return [
            {
                "id": row["id"],
                "language": row["language"],
                "wrappers": json.loads(str(row["wrappers_json"])),
                "strategy": row["strategy"],
                "path": row["path"],
                "enabled": bool(row["enabled"]),
                "config": json.loads(str(row["config_json"])),
            }
            for row in rows
        ]

    def get_resolver_profile(self, profile_id: str) -> Dict[str, object]:
        row = self.con.execute(
            """
            select id, language, wrappers_json, strategy, path, enabled, config_json
            from resolver_profiles
            where id = ?
            """,
            (profile_id,),
        ).fetchone()
        if row is None:
            raise KeyError(profile_id)
        return {
            "id": row["id"],
            "language": row["language"],
            "wrappers": json.loads(str(row["wrappers_json"])),
            "strategy": row["strategy"],
            "path": row["path"],
            "enabled": bool(row["enabled"]),
            "config": json.loads(str(row["config_json"])),
        }

    def save_provider_settings(self, settings: Dict[str, object], settings_id: str = "default") -> None:
        self.con.execute(
            """
            insert into provider_settings(id, settings_json)
            values (?, ?)
            on conflict(id) do update set settings_json=excluded.settings_json
            """,
            (settings_id, json.dumps(settings)),
        )
        self.con.commit()

    def load_provider_settings(self, settings_id: str = "default") -> Dict[str, object]:
        row = self.con.execute("select settings_json from provider_settings where id = ?", (settings_id,)).fetchone()
        if row is None:
            return {}
        return json.loads(str(row["settings_json"]))

    def search_vector(self, vector: List[float], limit: int = 5) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select
              embeddings.chunk_id,
              embeddings.provider,
              embeddings.model,
              embeddings.vector_json,
              chunks.text,
              documents.path
            from embeddings
            join chunks on chunks.id = embeddings.chunk_id
            join documents on documents.id = chunks.document_id
            """
        )
        scored = []
        for row in rows:
            stored_vector = json.loads(str(row["vector_json"]))
            scored.append(
                {
                    "chunk_id": int(row["chunk_id"]),
                    "provider": row["provider"],
                    "model": row["model"],
                    "text": row["text"],
                    "path": row["path"],
                    "score": _cosine_similarity(vector, stored_vector),
                }
            )
        return sorted(scored, key=lambda item: float(item["score"]), reverse=True)[:limit]

    def expand_graph(self, symbol: str, hops: int = 1) -> Dict[str, List[Dict[str, object]]]:
        seen = {symbol}
        frontier = {symbol}
        edges: List[Dict[str, object]] = []

        for _ in range(max(1, hops)):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self.con.execute(
                f"""
                select src, dst, relation, confidence
                from edges
                where src in ({placeholders}) or dst in ({placeholders})
                order by confidence desc
                """,
                tuple(frontier) + tuple(frontier),
            )
            next_frontier = set()
            for row in rows:
                edge = dict(row)
                edges.append(edge)
                for endpoint in (str(row["src"]), str(row["dst"])):
                    if endpoint not in seen:
                        seen.add(endpoint)
                        next_frontier.add(endpoint)
            frontier = next_frontier

        deduped_edges = list({(edge["src"], edge["dst"], edge["relation"]): edge for edge in edges}.values())
        return {
            "nodes": [{"id": node} for node in sorted(seen)],
            "edges": deduped_edges,
        }

    def expand_graph_networkx(self, symbol: str, hops: int = 1) -> Dict[str, object]:
        graph = self.to_networkx()
        seen = {symbol}
        frontier = {symbol}

        for _ in range(max(1, hops)):
            next_frontier = set()
            for node in frontier:
                if node not in graph:
                    continue
                neighbors = set(graph.successors(node)) | set(graph.predecessors(node))
                next_frontier.update(neighbor for neighbor in neighbors if neighbor not in seen)
            if not next_frontier:
                break
            seen.update(next_frontier)
            frontier = next_frontier

        subgraph = graph.subgraph(seen)
        edges = [
            {
                "src": src,
                "dst": dst,
                "relation": data["relation"],
                "confidence": float(data["confidence"]),
            }
            for src, dst, data in subgraph.edges(data=True)
        ]
        edges.sort(
            key=lambda edge: (-float(edge["confidence"]), str(edge["src"]), str(edge["dst"]), str(edge["relation"]))
        )
        return {
            "nodes": [{"id": node} for node in sorted(seen)],
            "edges": edges,
            "graph_runtime": "networkx",
        }

    def global_graph_networkx(self, limit: int = 100) -> Dict[str, object]:
        edge_limit = max(0, int(limit))
        edge_stats: Dict[tuple[str, str, str], Dict[str, object]] = {}
        node_kinds: Dict[str, str] = {}

        def remember_node(node_id: str, kind: str) -> None:
            if node_id and kind:
                node_kinds.setdefault(node_id, _normalize_graph_kind(kind))

        def add_edge(src: str, dst: str, relation: str, confidence: float, src_kind: str, dst_kind: str) -> None:
            src = src.strip()
            dst = dst.strip()
            relation = relation.strip() or "related"
            if not src or not dst or src == dst:
                return
            bounded_confidence = max(0.05, min(1.0, float(confidence or 0.5)))
            key = (src, dst, relation)
            stats = edge_stats.setdefault(key, {"confidence_sum": 0.0, "count": 0})
            stats["confidence_sum"] = float(stats["confidence_sum"]) + bounded_confidence
            stats["count"] = int(stats["count"]) + 1
            remember_node(src, src_kind)
            remember_node(dst, dst_kind)

        for row in self.con.execute("select src, dst, relation, confidence from edges"):
            add_edge(
                str(row["src"]),
                str(row["dst"]),
                str(row["relation"]),
                float(row["confidence"]),
                _kind_for_graph_symbol(str(row["src"])),
                _kind_for_graph_symbol(str(row["dst"])),
            )

        symbols_by_chunk: Dict[int, List[tuple[str, str, float]]] = {}
        evidence_rows = self.con.execute(
            """
            select
              evidence.chunk_id,
              evidence.corpus_id,
              evidence.source_type,
              evidence.path,
              evidence.line_start,
              evidence.page,
              evidence.symbol,
              evidence.entity_type,
              evidence.access_type,
              evidence.confidence,
              chunks.text as chunk_text,
              corpora.source_root as source_root
            from evidence
            join chunks on chunks.id = evidence.chunk_id
            left join corpora on corpora.id = evidence.corpus_id
            order by evidence.chunk_id, evidence.confidence desc, evidence.id asc
            """
        )
        function_cache: Dict[tuple[str, str, int, str], str] = {}
        for row in evidence_rows:
            symbol = str(row["symbol"])
            entity_type = str(row["entity_type"] or "")
            source_type = str(row["source_type"] or "code")
            if not _is_meaningful_graph_symbol(symbol, entity_type):
                continue
            confidence = float(row["confidence"] or 0.5)
            symbol_kind = _kind_for_graph_evidence(source_type, entity_type, symbol)
            path = str(row["path"] or "")
            path_kind = _normalize_graph_kind(source_type)
            add_edge(symbol, path, f"appears_in_{path_kind}", confidence * 0.74, symbol_kind, path_kind)
            section_id, section_kind = _section_node_for_graph_row(row)
            if section_id:
                add_edge(
                    section_id,
                    symbol,
                    "section_mentions",
                    confidence * 0.92,
                    section_kind,
                    symbol_kind,
                )
            if source_type == "code":
                function_name = _function_context_for_graph_row(row, function_cache)
                if function_name:
                    add_edge(
                        function_name,
                        symbol,
                        _operation_relation_for_graph(str(row["access_type"] or "mention")),
                        confidence * 0.98,
                        "code",
                        symbol_kind,
                    )
                    add_edge(function_name, path, "defined_in", confidence * 0.56, "code", path_kind)
            chunk_id = int(row["chunk_id"])
            chunk_symbols = symbols_by_chunk.setdefault(chunk_id, [])
            if not any(existing_symbol == symbol for existing_symbol, _kind, _confidence in chunk_symbols):
                chunk_symbols.append((symbol, symbol_kind, confidence))

        for chunk_symbols in symbols_by_chunk.values():
            ranked = chunk_symbols[:8]
            for left, right in combinations(ranked, 2):
                src, dst = _ordered_graph_pair(left, right)
                add_edge(
                    src[0],
                    dst[0],
                    "co_occurs",
                    (src[2] + dst[2]) / 2,
                    src[1],
                    dst[1],
                )

        edges = []
        for (src, dst, relation), stats in edge_stats.items():
            count = int(stats["count"])
            average_confidence = float(stats["confidence_sum"]) / max(1, count)
            frequency_boost = min(0.35, math.log1p(count) / 12) if count > 1 else 0.0
            weight = min(1.0, average_confidence + frequency_boost)
            edges.append(
                {
                    "src": src,
                    "dst": dst,
                    "relation": relation,
                    "confidence": round(min(1.0, average_confidence), 4),
                    "weight": round(weight, 4),
                    "count": count,
                }
            )
        edges.sort(
            key=lambda edge: (
                _graph_relation_priority(str(edge["relation"])),
                -float(edge["weight"]),
                -int(edge["count"]),
                -float(edge["confidence"]),
                str(edge["src"]),
                str(edge["dst"]),
                str(edge["relation"]),
            )
        )
        selected_edges = edges[:edge_limit]
        node_weights: Dict[str, float] = {}
        for edge in selected_edges:
            weight = float(edge["weight"])
            node_weights[str(edge["src"])] = node_weights.get(str(edge["src"]), 0.0) + weight
            node_weights[str(edge["dst"])] = node_weights.get(str(edge["dst"]), 0.0) + weight
        nodes = [
            {
                "id": node,
                "kind": node_kinds.get(node, _kind_for_graph_symbol(node)),
                "weight": round(weight, 4),
            }
            for node, weight in sorted(node_weights.items(), key=lambda item: (-item[1], item[0]))
        ]
        return {
            "nodes": nodes,
            "edges": selected_edges,
            "graph_runtime": "networkx",
        }

    def to_networkx(self):
        import networkx as nx

        graph = nx.DiGraph()
        rows = self.con.execute("select src, dst, relation, confidence from edges")
        for row in rows:
            graph.add_edge(
                str(row["src"]),
                str(row["dst"]),
                relation=row["relation"],
                confidence=float(row["confidence"]),
            )
        return graph


def _cosine_similarity(left: List[float], right: List[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


_GRAPH_STOP_WORDS = {
    "THE",
    "AND",
    "FOR",
    "WITH",
    "WITHOUT",
    "WARRANTY",
    "WARRANTIES",
    "SOFTWARE",
    "PURPOSE",
    "PROVIDED",
    "SHALL",
    "OTHER",
    "OTHERWISE",
    "PARTICULAR",
    "TORT",
}


def _is_meaningful_graph_symbol(symbol: str, entity_type: str) -> bool:
    if len(symbol) < 3 or symbol.upper() in _GRAPH_STOP_WORDS:
        return False
    if "->" in symbol or "_" in symbol or re.search(r"\d", symbol):
        return True
    if symbol.startswith(("reg", "mm", "RREG", "WREG", "REG_")):
        return True
    return entity_type in {"register", "field", "macro", "context"} and len(symbol) > 3


def _normalize_graph_kind(kind: str) -> str:
    normalized = kind.lower()
    if normalized in {"register", "macro"}:
        return "register"
    if normalized in {"field"}:
        return "field"
    if normalized in {"doc_section", "section"}:
        return "doc_section"
    if normalized in {"pdf_section", "pdf_page"}:
        return "pdf_section"
    if normalized in {"doc"}:
        return "doc"
    if normalized in {"pdf"}:
        return "pdf"
    return "code"


def _kind_for_graph_symbol(symbol: str) -> str:
    if re.search(r"ENABLE|DISABLE|PENDING|MASK|SHIFT|RESET_REQUEST|INVALIDATE|FIELD", symbol):
        return "field"
    if symbol.startswith(("reg", "mm", "RREG", "WREG", "REG_")) or re.search(
        r"CNTL|STATUS|RESET|BASE|SIZE|VMID|DOORBELL|QUEUE",
        symbol,
    ):
        return "register"
    return "code"


def _kind_for_graph_evidence(source_type: str, entity_type: str, symbol: str) -> str:
    if entity_type in {"register", "field", "macro", "context"}:
        return _normalize_graph_kind(entity_type)
    inferred = _kind_for_graph_symbol(symbol)
    if inferred != "code":
        return inferred
    return _normalize_graph_kind(source_type)


def _ordered_graph_pair(
    left: tuple[str, str, float],
    right: tuple[str, str, float],
) -> tuple[tuple[str, str, float], tuple[str, str, float]]:
    priority = {"register": 0, "field": 1, "code": 2, "doc": 3, "pdf": 3}
    left_key = (priority.get(left[1], 9), left[0])
    right_key = (priority.get(right[1], 9), right[0])
    return (left, right) if left_key <= right_key else (right, left)


def _operation_relation_for_graph(access_type: str) -> str:
    if access_type in {"field_set", "read", "write", "read_modify_write"}:
        return access_type
    return "mentions"


def _section_node_for_graph_row(row: sqlite3.Row) -> tuple[str, str]:
    source_type = str(row["source_type"] or "")
    if source_type not in {"doc", "pdf"}:
        return "", ""
    path = str(row["path"] or "").strip()
    if not path:
        return "", ""
    chunk_text = str(row["chunk_text"] or "")
    heading = _first_markdown_heading(chunk_text)
    if heading:
        return f"{path}#{_slug_for_graph_heading(heading)}", "doc_section" if source_type == "doc" else "pdf_section"
    if source_type == "pdf":
        page = int(row["page"] or 0) if "page" in row.keys() else 0
        if page:
            return f"{path}#page-{page}", "pdf_section"
    line_start = int(row["line_start"] or 0)
    if line_start:
        return f"{path}#lines-{line_start}", "doc_section" if source_type == "doc" else "pdf_section"
    return f"{path}#section", "doc_section" if source_type == "doc" else "pdf_section"


def _first_markdown_heading(text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(?:\d+:\s*)?#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip().strip("#").strip()
    return ""


def _slug_for_graph_heading(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    return slug or "section"


def _graph_relation_priority(relation: str) -> int:
    if relation in {"field_set", "read", "write", "read_modify_write", "sets_field"}:
        return 0
    if relation in {"has_field", "used_by", "calls", "wraps", "maps_base", "documented_by"}:
        return 1
    if relation == "section_mentions":
        return 2
    if relation == "co_occurs":
        return 3
    if relation.startswith("appears_in"):
        return 4
    if relation == "defined_in":
        return 5
    return 6


def _function_context_for_graph_row(
    row: sqlite3.Row,
    cache: Dict[tuple[str, str, int, str], str],
) -> str:
    path = str(row["path"] or "")
    source_root = str(row["source_root"] or "")
    line_start = int(row["line_start"] or 0)
    chunk_text = str(row["chunk_text"] or "")
    cache_key = (source_root, path, line_start, chunk_text[:80])
    if cache_key in cache:
        return cache[cache_key]

    function_name = ""
    if path and source_root:
        candidate = (Path(source_root).expanduser() / path).resolve()
        if candidate.exists() and candidate.is_file():
            function_name = _function_name_from_source_file(candidate, line_start)
    if not function_name:
        function_name = _function_name_from_chunk_text(chunk_text)
    cache[cache_key] = function_name
    return function_name


def _function_name_from_source_file(file_path: Path, line_start: int) -> str:
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    end = min(max(1, line_start), len(lines))
    start = max(0, end - 800)
    return _last_function_name_in_text("\n".join(lines[start:end]))


def _function_name_from_chunk_text(text: str) -> str:
    cleaned = re.sub(r"(?m)^\s*\d+:\s?", "", text)
    return _last_function_name_in_text(cleaned)


def _last_function_name_in_text(text: str) -> str:
    pattern = re.compile(
        r"(?ms)^\s*(?:static\s+)?(?:inline\s+)?(?:[A-Za-z_][\w\s\*]*\s+)+(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
    )
    ignored = {"if", "for", "while", "switch", "return", "sizeof"}
    matches = [match.group("name") for match in pattern.finditer(text)]
    for name in reversed(matches):
        if name not in ignored:
            return name
    return ""
