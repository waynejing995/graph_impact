"""SQLite evidence storage and graph expansion utilities."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .graph_filters import is_resolver_wrapper_name


@dataclass
class AsipStore:
    con: sqlite3.Connection

    @classmethod
    def connect(cls, path: str) -> "AsipStore":
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        try:
            con.execute("pragma journal_mode = wal")
            con.execute("pragma synchronous = normal")
        except sqlite3.DatabaseError:
            pass
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
              confidence real not null,
              stage text not null default 'deterministic',
              source text not null default '',
              path text not null default '',
              line_start integer,
              line_end integer,
              provenance_json text not null default '{}'
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

            create index if not exists idx_evidence_chunk_confidence
              on evidence(chunk_id, confidence desc, id asc);
            create index if not exists idx_edges_src_stage
              on edges(src, stage);
            create index if not exists idx_edges_dst_stage
              on edges(dst, stage);
            create index if not exists idx_edges_stage
              on edges(stage);
            """
        )
        self._ensure_column("chunks", "page", "integer")
        self._ensure_column("jobs", "metadata_json", "text not null default '{}'")
        self._ensure_column("edges", "stage", "text not null default 'deterministic'")
        self._ensure_column("edges", "source", "text not null default ''")
        self._ensure_column("edges", "path", "text not null default ''")
        self._ensure_column("edges", "line_start", "integer")
        self._ensure_column("edges", "line_end", "integer")
        self._ensure_column("edges", "provenance_json", "text not null default '{}'")
        self._ensure_column("resolver_profiles", "config_json", "text not null default '{}'")
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
            f"select id, path from documents where corpus_id in ({placeholders})",
            tuple(ids),
        ).fetchall()
        document_ids = [int(row["id"]) for row in document_rows]
        document_paths = [str(row["path"]) for row in document_rows if str(row["path"] or "")]
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
        if document_paths:
            path_placeholders = ",".join("?" for _ in document_paths)
            self.con.execute(f"delete from edges where path in ({path_placeholders})", tuple(document_paths))
        for corpus_id in ids:
            self.con.execute(
                "delete from edges where provenance_json like ?",
                (f'%"corpus_id": "{corpus_id}"%',),
            )
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
        commit: bool = True,
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
        if commit:
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

    def find_evidence_candidates(
        self,
        tokens: Iterable[str],
        fts_chunk_ids: Iterable[int],
        limit: int,
        max_query_tokens: Optional[int] = None,
    ) -> List[Dict[str, object]]:
        token_list = [str(token).lower() for token in tokens if token]
        chunk_ids = list(dict.fromkeys(int(chunk_id) for chunk_id in fts_chunk_ids))
        candidate_limit = max(1, int(limit))
        ranked_tokens = token_list if max_query_tokens is None else token_list[:max(0, int(max_query_tokens))]
        if chunk_ids:
            chunk_rows = self._find_evidence_candidates_by_chunks(chunk_ids, candidate_limit)
            if len(chunk_rows) >= candidate_limit:
                return chunk_rows
            fallback_limit = candidate_limit - len(chunk_rows)
            like_rows = self._find_evidence_candidates_by_like(
                ranked_tokens,
                fallback_limit,
                exclude_ids=[int(row["id"]) for row in chunk_rows],
            )
            return [*chunk_rows, *like_rows]
        if not ranked_tokens:
            return self.all_evidence()
        return self._find_evidence_candidates_by_like(ranked_tokens, candidate_limit)

    def _find_evidence_candidates_by_chunks(
        self,
        chunk_ids: Iterable[int],
        limit: int,
    ) -> List[Dict[str, object]]:
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
            limit ?
            """,
            (*ids, max(1, int(limit))),
        )
        return self._append_missing_source_rows_for_chunks([dict(row) for row in rows], ids)

    def _append_missing_source_rows_for_chunks(
        self,
        rows: List[Dict[str, object]],
        chunk_ids: Iterable[int],
    ) -> List[Dict[str, object]]:
        ids = list(dict.fromkeys(int(chunk_id) for chunk_id in chunk_ids))
        if not ids:
            return rows
        selected_ids = {int(row["id"]) for row in rows if row.get("id") not in (None, "")}
        selected_sources = {str(row.get("source_type") or "") for row in rows}
        placeholders = ",".join("?" for _ in ids)
        for source_type in ("code", "doc", "pdf", "register"):
            if source_type in selected_sources:
                continue
            row = self.con.execute(
                f"""
                select
                  id, chunk_id, corpus_id, source_type, repo, path, line_start, line_end, page,
                  symbol, entity_type, ip_block, asic_or_generation, access_type,
                  confidence, snippet, resolved_chain, query_id
                from evidence
                where chunk_id in ({placeholders})
                  and source_type = ?
                order by confidence desc, id asc
                limit 1
                """,
                (*ids, source_type),
            ).fetchone()
            if row is None or int(row["id"]) in selected_ids:
                continue
            rows.append(dict(row))
            selected_ids.add(int(row["id"]))
            selected_sources.add(source_type)
        return rows

    def _find_evidence_candidates_by_like(
        self,
        ranked_tokens: Iterable[str],
        limit: int,
        exclude_ids: Optional[Iterable[int]] = None,
    ) -> List[Dict[str, object]]:
        token_conditions: List[str] = []
        params: List[object] = []
        for token in ranked_tokens:
            like = f"%{token}%"
            token_conditions.append(
                "(lower(symbol) like ? or lower(path) like ? or lower(snippet) like ? or lower(resolved_chain) like ?)"
            )
            params.extend([like, like, like, like])
        if not token_conditions:
            return []
        conditions = [f"({' or '.join(token_conditions)})"]
        excluded = list(dict.fromkeys(int(row_id) for row_id in (exclude_ids or [])))
        if excluded:
            placeholders = ",".join("?" for _ in excluded)
            conditions.append(f"id not in ({placeholders})")
            params.extend(excluded)
        params.append(max(1, int(limit)))
        rows = self.con.execute(
            f"""
            select
              id, chunk_id, corpus_id, source_type, repo, path, line_start, line_end, page,
              symbol, entity_type, ip_block, asic_or_generation, access_type,
              confidence, snippet, resolved_chain, query_id
            from evidence
            where {" and ".join(conditions)}
            order by confidence desc, id asc
            limit ?
            """,
            tuple(params),
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

    def add_edge(
        self,
        src: str,
        dst: str,
        relation: str,
        confidence: float,
        stage: str = "deterministic",
        source: str = "",
        path: str = "",
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        provenance: Optional[Dict[str, object]] = None,
        commit: bool = True,
    ) -> int:
        if _is_graph_wrapper_hub(src) or _is_graph_wrapper_hub(dst):
            return 0
        cursor = self.con.execute(
            """
            insert into edges(
              src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                src,
                dst,
                relation,
                confidence,
                stage or "deterministic",
                source or "",
                path or "",
                line_start,
                line_end,
                json.dumps(provenance or {}),
            ),
        )
        if commit:
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

    def search_vector(self, vector: List[float], limit: int) -> List[Dict[str, object]]:
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
        if _is_graph_wrapper_hub(symbol):
            return {"nodes": [], "edges": []}
        seen = {symbol}
        frontier = {symbol}
        edges: List[Dict[str, object]] = []

        for _ in range(max(1, hops)):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self.con.execute(
                f"""
                select src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json
                from edges
                where src in ({placeholders}) or dst in ({placeholders})
                order by confidence desc
                """,
                tuple(frontier) + tuple(frontier),
            )
            next_frontier = set()
            for row in rows:
                if _is_graph_wrapper_hub(str(row["src"])) or _is_graph_wrapper_hub(str(row["dst"])):
                    continue
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

    def expand_graph_networkx(
        self,
        symbol: str,
        hops: int = 1,
        include_evidence_derived: bool = False,
    ) -> Dict[str, object]:
        if _is_graph_wrapper_hub(symbol):
            return {"nodes": [], "edges": [], "graph_runtime": "networkx"}
        if not self._has_expandable_edges(include_evidence_derived=include_evidence_derived):
            return _single_seed_graph(symbol)
        graph = self.to_networkx(include_evidence_derived=include_evidence_derived)
        seen = {symbol}
        frontier = {symbol}

        for _ in range(max(1, hops)):
            next_frontier = set()
            for node in frontier:
                if node not in graph:
                    continue
                if node != symbol and _is_graph_wrapper_hub(str(node)):
                    continue
                neighbors = set(graph.successors(node)) | set(graph.predecessors(node))
                next_frontier.update(neighbor for neighbor in neighbors if neighbor not in seen)
            if not next_frontier:
                break
            seen.update(next_frontier)
            frontier = next_frontier

        subgraph = graph.subgraph(seen)
        subgraph_edges = list(subgraph.edges(data=True))
        has_semantic_edges = any(str(data.get("stage") or "") == "semantic" for _src, _dst, data in subgraph_edges)
        edges = []
        node_ids = set()
        node_payloads: Dict[str, Dict[str, object]] = {}
        known_function_metadata = self._known_graph_function_metadata() if has_semantic_edges else {}
        known_function_symbols = set(known_function_metadata)
        for src, dst, data in subgraph_edges:
            src_metadata = _metadata_from_networkx_edge_data(data, str(src))
            dst_metadata = _metadata_from_networkx_edge_data(data, str(dst))
            stage = str(data.get("stage") or "deterministic")
            if stage == "semantic":
                src_metadata = _merge_graph_metadata(known_function_metadata.get(str(src), {}), src_metadata)
                dst_metadata = _merge_graph_metadata(known_function_metadata.get(str(dst), {}), dst_metadata)
            semantic_functions = known_function_symbols if stage == "semantic" else None
            src_node = _product_graph_node(
                str(src),
                _kind_for_graph_symbol(str(src)),
                src_metadata,
                known_function_symbols=semantic_functions,
            )
            dst_node = _product_graph_node(
                str(dst),
                _kind_for_graph_symbol(str(dst)),
                dst_metadata,
                known_function_symbols=semantic_functions,
            )
            relation = _normalize_graph_relation(str(data["relation"]))
            if src_node is None or dst_node is None or not relation:
                continue
            fields = _dedupe_strings(
                [
                    *_string_values(src_metadata.get("field")),
                    *_string_values(src_metadata.get("fields")),
                    *_string_values(dst_metadata.get("field")),
                    *_string_values(dst_metadata.get("fields")),
                ]
            )
            resolver_wrappers = _dedupe_strings(
                [
                    *_string_values(src_metadata.get("wrapper")),
                    *_string_values(src_metadata.get("resolver_wrappers")),
                    *_string_values(dst_metadata.get("wrapper")),
                    *_string_values(dst_metadata.get("resolver_wrappers")),
                ]
            )
            edge = {
                "src": str(src_node["id"]),
                "dst": str(dst_node["id"]),
                "relation": relation,
                "confidence": float(data["confidence"]),
                "stage": stage,
                "source": data.get("source", ""),
                "attr": {
                    "source": _dedupe_source_records(
                        [*_source_records_for_graph(src_metadata), *_source_records_for_graph(dst_metadata)]
                    ),
                    "fields": fields,
                    "resolver_wrappers": resolver_wrappers,
                },
            }
            edges.append(edge)
            node_ids.add(edge["src"])
            node_ids.add(edge["dst"])
            node_payloads[edge["src"]] = _boxmatrix_node_payload(
                edge["src"],
                str(src_node["kind"]),
                1,
                src_node,
            )
            node_payloads[edge["dst"]] = _boxmatrix_node_payload(
                edge["dst"],
                str(dst_node["kind"]),
                1,
                dst_node,
            )
        if not node_ids:
            seed_node = _product_graph_node(symbol, _kind_for_graph_symbol(symbol), {})
            if seed_node is not None:
                node_ids.add(str(seed_node["id"]))
                node_payloads[str(seed_node["id"])] = _boxmatrix_node_payload(
                    str(seed_node["id"]),
                    str(seed_node["kind"]),
                    1,
                    seed_node,
                )
        edges.sort(
            key=lambda edge: (-float(edge["confidence"]), str(edge["src"]), str(edge["dst"]), str(edge["relation"]))
        )
        return {
            "nodes": [node_payloads[node] for node in sorted(node_ids)],
            "edges": edges,
            "graph_runtime": "networkx",
        }

    def global_graph_networkx(
        self,
        limit: Optional[int] = None,
        include_evidence_derived: bool = False,
        evidence_row_cap: Optional[int] = None,
        cooccurrence_symbol_limit: Optional[int] = None,
    ) -> Dict[str, object]:
        edge_limit = None if limit is None else max(0, int(limit))
        evidence_cap = 0 if evidence_row_cap is None else max(0, int(evidence_row_cap))
        cooccurrence_limit = None if cooccurrence_symbol_limit is None else max(0, int(cooccurrence_symbol_limit))
        edge_stats: Dict[tuple[str, str, str], Dict[str, object]] = {}
        node_kinds: Dict[str, str] = {}
        node_metadata: Dict[str, Dict[str, object]] = {}
        known_function_metadata: Optional[Dict[str, Dict[str, object]]] = None
        known_function_symbols: Optional[set[str]] = None

        def semantic_function_metadata() -> tuple[Dict[str, Dict[str, object]], set[str]]:
            nonlocal known_function_metadata, known_function_symbols
            if known_function_metadata is None:
                known_function_metadata = self._known_graph_function_metadata()
                known_function_symbols = set(known_function_metadata)
            return known_function_metadata, known_function_symbols or set()

        def remember_node(node: Mapping[str, object]) -> None:
            node_id = str(node.get("id") or "")
            kind = str(node.get("kind") or "")
            if not node_id or not kind:
                return
            node_kinds.setdefault(node_id, _normalize_graph_kind(kind))
            existing = node_metadata.setdefault(node_id, _empty_boxmatrix_metadata(node_id, kind))
            _merge_boxmatrix_metadata(existing, node)

        def add_edge(
            src: str,
            dst: str,
            relation: str,
            confidence: float,
            src_kind: str,
            dst_kind: str,
            stage: str = "deterministic",
            source: str = "",
            src_metadata: Optional[Dict[str, object]] = None,
            dst_metadata: Optional[Dict[str, object]] = None,
        ) -> None:
            src = src.strip()
            dst = dst.strip()
            original_relation = relation.strip() or "relates_to"
            relation = _normalize_graph_relation(original_relation)
            if relation == "":
                return
            if not src or not dst or src == dst:
                return
            if _is_graph_wrapper_hub(src) or _is_graph_wrapper_hub(dst):
                return
            if stage == "semantic":
                semantic_metadata, semantic_symbols = semantic_function_metadata()
                src_metadata = _merge_graph_metadata(semantic_metadata.get(src, {}), src_metadata)
                dst_metadata = _merge_graph_metadata(semantic_metadata.get(dst, {}), dst_metadata)
                semantic_functions = semantic_symbols
            else:
                semantic_functions = None
            src_node = _product_graph_node(src, src_kind, src_metadata, known_function_symbols=semantic_functions)
            dst_node = _product_graph_node(dst, dst_kind, dst_metadata, known_function_symbols=semantic_functions)
            if src_node is None or dst_node is None:
                folded_node = _fold_field_endpoint_into_register(
                    src,
                    dst,
                    relation,
                    src_kind,
                    dst_kind,
                    src_node,
                    dst_node,
                    src_metadata,
                    dst_metadata,
                )
                if folded_node is not None:
                    remember_node(folded_node)
                return
            src = str(src_node["id"])
            dst = str(dst_node["id"])
            if src == dst:
                return
            bounded_confidence = max(0.05, min(1.0, float(confidence or 0.5)))
            key = (src, dst, relation)
            stats = edge_stats.setdefault(
                key,
                {
                    "confidence_sum": 0.0,
                    "count": 0,
                    "stages": set(),
                    "sources": set(),
                    "fields": set(),
                    "resolver_wrappers": set(),
                    "original_relations": set(),
                    "source_records": [],
                },
            )
            stats["confidence_sum"] = float(stats["confidence_sum"]) + bounded_confidence
            stats["count"] = int(stats["count"]) + 1
            stats["stages"].add(stage or "deterministic")
            if source:
                stats["sources"].add(source)
            if original_relation != relation:
                stats["original_relations"].add(original_relation)
            _merge_edge_attr_stats(stats, src_node)
            _merge_edge_attr_stats(stats, dst_node)
            remember_node(src_node)
            remember_node(dst_node)

        had_persisted_graph_rows = False
        for row in self.con.execute(
            "select src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json from edges"
        ):
            if str(row["stage"] or "") == "evidence" and not include_evidence_derived:
                continue
            had_persisted_graph_rows = True
            src = str(row["src"])
            dst = str(row["dst"])
            add_edge(
                src,
                dst,
                str(row["relation"]),
                float(row["confidence"]),
                _kind_for_graph_symbol(src),
                _kind_for_graph_symbol(dst),
                str(row["stage"] or "deterministic"),
                str(row["source"] or ""),
                src_metadata=_metadata_from_edge_provenance(row, src),
                dst_metadata=_metadata_from_edge_provenance(row, dst),
            )

        symbols_by_chunk: Dict[int, List[tuple[str, str, float]]] = {}
        evidence_rows = []
        should_derive_evidence = include_evidence_derived or not had_persisted_graph_rows
        if should_derive_evidence and self._evidence_row_count_within_cap(evidence_cap):
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
                  evidence.snippet,
                  evidence.resolved_chain,
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
                    src_metadata=_section_metadata_for_graph_row(row, section_id),
                    dst_metadata=_metadata_for_graph_evidence_row(row, symbol),
                )
            if source_type == "code":
                function_name = _function_context_for_graph_row(row, function_cache)
                if function_name:
                    target_symbol = symbol
                    target_kind = symbol_kind
                    target_metadata = _metadata_for_graph_evidence_row(row, symbol)
                    if symbol_kind == "field":
                        owner_register = _register_for_field_evidence_row(row)
                        if owner_register:
                            target_symbol = owner_register
                            target_kind = "register"
                            target_metadata = _metadata_for_graph_evidence_row(row, owner_register)
                            target_metadata["field"] = symbol
                    add_edge(
                        function_name,
                        target_symbol,
                        _operation_relation_for_graph(str(row["access_type"] or "mention")),
                        confidence * 0.98,
                        "code",
                        target_kind,
                        src_metadata=_metadata_for_graph_evidence_row(row, function_name),
                        dst_metadata=target_metadata,
                    )
            chunk_id = int(row["chunk_id"])
            chunk_symbols = symbols_by_chunk.setdefault(chunk_id, [])
            if not any(existing_symbol == symbol for existing_symbol, _kind, _confidence in chunk_symbols):
                chunk_symbols.append((symbol, symbol_kind, confidence))

        for chunk_symbols in symbols_by_chunk.values():
            ranked = chunk_symbols if cooccurrence_limit is None else chunk_symbols[:cooccurrence_limit]
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
            stages = sorted(str(stage) for stage in stats["stages"])
            sources = sorted(str(source) for source in stats["sources"])
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
                    "stage": stages[0] if len(stages) == 1 else "mixed",
                    "sources": sources,
                    "attr": _edge_attr_payload(stats),
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
        selected_edges = edges if edge_limit is None else _select_global_graph_edges(edges, edge_limit)
        node_weights: Dict[str, float] = {}
        for edge in selected_edges:
            weight = float(edge["weight"])
            node_weights[str(edge["src"])] = node_weights.get(str(edge["src"]), 0.0) + weight
            node_weights[str(edge["dst"])] = node_weights.get(str(edge["dst"]), 0.0) + weight
            _append_boxmatrix_io(node_metadata, edge)
        if not selected_edges:
            for node in node_metadata:
                node_weights[node] = max(node_weights.get(node, 0.0), 1.0)
        nodes = [
            _boxmatrix_node_payload(
                node,
                node_kinds.get(node, _kind_for_graph_symbol(node)),
                round(weight, 4),
                node_metadata.get(node),
            )
            for node, weight in sorted(node_weights.items(), key=lambda item: (-item[1], item[0]))
        ]
        return {
            "nodes": nodes,
            "edges": selected_edges,
            "graph_runtime": "networkx",
        }

    def _evidence_row_count_within_cap(self, cap: int) -> bool:
        if cap <= 0:
            return False
        if not self._table_exists("evidence"):
            return False
        rows = self.con.execute("select id from evidence limit ?", (cap + 1,)).fetchall()
        return len(rows) <= cap

    def _has_expandable_edges(self, include_evidence_derived: bool = False) -> bool:
        if not self._table_exists("edges"):
            return False
        if include_evidence_derived:
            row = self.con.execute("select 1 from edges limit 1").fetchone()
        else:
            row = self.con.execute("select 1 from edges where stage <> 'evidence' limit 1").fetchone()
        return row is not None

    def _known_graph_function_metadata(self) -> Dict[str, Dict[str, object]]:
        functions: Dict[str, Dict[str, object]] = {}
        if self._table_exists("evidence"):
            rows = self.con.execute(
                """
                select
                  symbol,
                  corpus_id,
                  source_type,
                  repo,
                  path,
                  line_start,
                  line_end,
                  snippet,
                  confidence
                from evidence
                where source_type = 'code' and entity_type = 'function'
                order by confidence desc, id asc
                """
            )
            for row in rows:
                symbol = str(row["symbol"] or "").strip()
                if not symbol or not _snippet_has_callable_symbol(str(row["snippet"] or ""), symbol):
                    continue
                metadata = functions.setdefault(
                    symbol,
                    {
                        "symbol": symbol,
                        "function_name": symbol,
                        "corpus_id": str(row["corpus_id"] or "unknown"),
                        "repo": str(row["repo"] or "unknown"),
                        "path": str(row["path"] or "unknown"),
                        "language": _language_for_graph_path(str(row["path"] or "")),
                    },
                )
                if row["line_start"] not in ("", None, 0):
                    metadata.setdefault("line_start", row["line_start"])
                if row["line_end"] not in ("", None, 0):
                    metadata.setdefault("line_end", row["line_end"])
        if self._table_exists("edges"):
            rows = self.con.execute(
                """
                select src, path, line_start, line_end, provenance_json
                from edges
                where stage = 'deterministic'
                """
            )
            for row in rows:
                try:
                    provenance = json.loads(str(row["provenance_json"] or "{}"))
                except json.JSONDecodeError:
                    provenance = {}
                symbol = str(provenance.get("function") or provenance.get("function_name") or "").strip()
                if not symbol:
                    continue
                metadata = functions.setdefault(
                    symbol,
                    {
                        "symbol": symbol,
                        "function_name": symbol,
                        "corpus_id": str(provenance.get("corpus_id") or "unknown"),
                        "repo": str(provenance.get("repo") or "unknown"),
                        "path": str(row["path"] or "unknown"),
                        "language": str(provenance.get("language") or _language_for_graph_path(str(row["path"] or ""))),
                    },
                )
                for key in ("corpus_id", "repo", "ip", "ip_version", "language"):
                    value = provenance.get(key)
                    if value not in ("", None, 0):
                        metadata.setdefault(key, value)
                if row["line_start"] not in ("", None, 0):
                    metadata.setdefault("line_start", row["line_start"])
                if row["line_end"] not in ("", None, 0):
                    metadata.setdefault("line_end", row["line_end"])
        return functions

    def _table_exists(self, name: str) -> bool:
        row = self.con.execute(
            "select 1 from sqlite_master where type = 'table' and name = ?",
            (name,),
        ).fetchone()
        return row is not None

    def to_networkx(self, include_evidence_derived: bool = False):
        import networkx as nx

        graph = nx.MultiDiGraph()
        rows = self.con.execute(
            "select src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json from edges"
        )
        for row in rows:
            if str(row["stage"] or "") == "evidence" and not include_evidence_derived:
                continue
            if _is_graph_wrapper_hub(str(row["src"])) or _is_graph_wrapper_hub(str(row["dst"])):
                continue
            graph.add_edge(
                str(row["src"]),
                str(row["dst"]),
                relation=row["relation"],
                confidence=float(row["confidence"]),
                stage=row["stage"],
                source=row["source"],
                path=row["path"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                provenance_json=row["provenance_json"],
            )
        return graph


def _product_graph_node(
    symbol: str,
    kind: str,
    metadata: Optional[Mapping[str, object]] = None,
    known_function_symbols: Optional[set[str]] = None,
) -> Optional[Dict[str, object]]:
    raw_metadata: Dict[str, object] = dict(metadata or {})
    if not raw_metadata:
        raw_metadata.update(_metadata_for_graph_symbol(symbol))
    normalized_kind = _normalize_graph_kind(kind)
    function_name = str(raw_metadata.get("function_name") or "").strip()
    if not function_name and symbol == str(raw_metadata.get("function") or ""):
        function_name = symbol
    if function_name:
        return _function_graph_node(symbol, function_name, raw_metadata)
    if normalized_kind in {"field", "doc", "pdf"}:
        return None
    if normalized_kind == "register":
        return _register_graph_node(symbol, raw_metadata)
    if normalized_kind in {"doc_section", "pdf_section", "doc_box"}:
        return _document_graph_node(symbol, normalized_kind, raw_metadata)
    if not function_name and _looks_like_function_symbol(symbol) and (
        known_function_symbols is None or symbol in known_function_symbols
    ):
        function_name = symbol
    if function_name:
        return _function_graph_node(symbol, function_name, raw_metadata)
    return None


def _single_seed_graph(symbol: str) -> Dict[str, object]:
    seed_node = _product_graph_node(symbol, _kind_for_graph_symbol(symbol), {})
    nodes = []
    if seed_node is not None:
        nodes.append(
            _boxmatrix_node_payload(
                str(seed_node["id"]),
                str(seed_node["kind"]),
                1,
                seed_node,
            )
        )
    return {"nodes": nodes, "edges": [], "graph_runtime": "networkx"}


def _register_graph_node(symbol: str, metadata: Mapping[str, object]) -> Dict[str, object]:
    register_symbol = _register_symbol_for_graph(str(metadata.get("symbol") or symbol))
    source = _source_records_for_graph(metadata)
    scope = _source_scope_for_graph(source)
    ip = str(metadata.get("ip") or _ip_for_graph_symbol(register_symbol, source) or "unknown")
    ip_version = str(metadata.get("ip_version") or _ip_version_for_graph_source(source) or "unknown")
    if ip_version == "unknown":
        node_id = f"register:{ip}:{ip_version}:{scope}:{register_symbol}"
    else:
        node_id = f"register:{ip}:{ip_version}:{register_symbol}"
    attr = {
        "source": source,
        "symbol": register_symbol,
        "ip": ip,
        "ip_version": ip_version,
        "fields": _string_values(metadata.get("fields"), metadata.get("field")),
        "resolver_wrappers": _string_values(metadata.get("resolver_wrappers"), metadata.get("wrapper")),
    }
    return {"id": node_id, "kind": "register", "label": register_symbol, "attr": attr, "in": [], "out": []}


def _function_graph_node(symbol: str, function_name: str, metadata: Mapping[str, object]) -> Dict[str, object]:
    source = _source_records_for_graph(metadata)
    primary_source = source[0]
    path = str(primary_source.get("path") or str(metadata.get("path") or "unknown"))
    scope = _source_scope_for_graph(source)
    node_id = f"function:{scope}:{path}:{function_name}"
    attr = {
        "source": source,
        "function_name": function_name,
        "language": str(metadata.get("language") or _language_for_graph_path(path)),
        "fields": _string_values(metadata.get("fields"), metadata.get("field")),
        "resolver_wrappers": _string_values(metadata.get("resolver_wrappers"), metadata.get("wrapper")),
    }
    return {"id": node_id, "kind": "function", "label": function_name, "attr": attr, "in": [], "out": []}


def _document_graph_node(symbol: str, kind: str, metadata: Mapping[str, object]) -> Dict[str, object]:
    source = _source_records_for_graph(metadata)
    attr = {
        "source": source,
        "anchor": str(metadata.get("anchor") or _anchor_for_graph_symbol(symbol)),
        "summary": str(metadata.get("summary") or ""),
        "fields": _string_values(metadata.get("fields"), metadata.get("field")),
        "resolver_wrappers": _string_values(metadata.get("resolver_wrappers"), metadata.get("wrapper")),
    }
    if kind == "doc_box":
        attr["box_id"] = str(metadata.get("box_id") or attr["anchor"] or Path(str(metadata.get("path") or symbol)).name)
        attr["inputs"] = _string_values(metadata.get("inputs"))
        attr["outputs"] = _string_values(metadata.get("outputs"))
        attr["constraints"] = _string_values(metadata.get("constraints"))
    else:
        attr["section_id"] = str(metadata.get("section_id") or attr["anchor"] or symbol)
        attr["title"] = str(metadata.get("title") or metadata.get("heading") or metadata.get("label") or Path(symbol).name)
    label = str(metadata.get("label") or attr.get("title") or attr.get("box_id") or symbol)
    return {"id": symbol, "kind": kind, "label": label, "attr": attr, "in": [], "out": []}


def _fold_field_endpoint_into_register(
    src: str,
    dst: str,
    relation: str,
    src_kind: str,
    dst_kind: str,
    src_node: Optional[Mapping[str, object]],
    dst_node: Optional[Mapping[str, object]],
    src_metadata: Optional[Mapping[str, object]],
    dst_metadata: Optional[Mapping[str, object]],
) -> Optional[Dict[str, object]]:
    if relation != "sets_field":
        return None
    if src_node is not None and _normalize_graph_kind(src_kind) == "register" and _normalize_graph_kind(dst_kind) == "field":
        folded = dict(src_node)
        attr = dict(folded.get("attr") if isinstance(folded.get("attr"), Mapping) else {})
        attr["fields"] = _dedupe_strings([*_string_values(attr.get("fields")), dst])
        folded["attr"] = attr
        return folded
    if dst_node is not None and _normalize_graph_kind(dst_kind) == "register" and _normalize_graph_kind(src_kind) == "field":
        folded = dict(dst_node)
        attr = dict(folded.get("attr") if isinstance(folded.get("attr"), Mapping) else {})
        attr["fields"] = _dedupe_strings([*_string_values(attr.get("fields")), src])
        folded["attr"] = attr
        return folded
    return None


def _empty_boxmatrix_metadata(node_id: str, kind: str) -> Dict[str, object]:
    return {
        "id": node_id,
        "kind": kind,
        "label": _label_for_graph_node_id(node_id),
        "in": [],
        "out": [],
        "attr": {"source": [_unknown_source_record()], "fields": [], "resolver_wrappers": []},
    }


def _boxmatrix_node_payload(
    node_id: str,
    kind: str,
    weight: float,
    metadata: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    payload = _empty_boxmatrix_metadata(node_id, kind)
    if metadata:
        _merge_boxmatrix_metadata(payload, metadata)
    payload["id"] = node_id
    payload["kind"] = _normalize_graph_kind(str(payload.get("kind") or kind))
    payload["label"] = str(payload.get("label") or _label_for_graph_node_id(node_id))
    payload["weight"] = weight
    attr = dict(payload.get("attr") if isinstance(payload.get("attr"), Mapping) else {})
    attr["source"] = _dedupe_source_records(attr.get("source") if isinstance(attr.get("source"), list) else [])
    if not attr["source"]:
        attr["source"] = [_unknown_source_record()]
    attr["fields"] = _dedupe_strings(_string_values(attr.get("fields")))
    attr["resolver_wrappers"] = _dedupe_strings(_string_values(attr.get("resolver_wrappers")))
    payload["attr"] = attr
    payload["in"] = _dedupe_strings(_string_values(payload.get("in")))
    payload["out"] = _dedupe_strings(_string_values(payload.get("out")))
    return payload


def _merge_boxmatrix_metadata(target: Dict[str, object], incoming: Mapping[str, object]) -> None:
    target["label"] = str(target.get("label") or incoming.get("label") or "")
    current_label = str(target.get("label") or "")
    current_id = str(target.get("id") or "")
    if incoming.get("label") and (
        not current_label
        or current_label == current_id
        or current_label == _label_for_graph_node_id(current_id)
        or current_label.startswith(("function:", "register:"))
    ):
        target["label"] = str(incoming["label"])
    target["kind"] = str(target.get("kind") or incoming.get("kind") or "")
    for direction in ("in", "out"):
        target[direction] = _dedupe_strings([*_string_values(target.get(direction)), *_string_values(incoming.get(direction))])
    target_attr = dict(target.get("attr") if isinstance(target.get("attr"), Mapping) else {})
    incoming_attr = dict(incoming.get("attr") if isinstance(incoming.get("attr"), Mapping) else {})
    for key, value in incoming.items():
        if key not in {"id", "kind", "label", "in", "out", "attr", "weight"} and value not in ("", None, 0):
            incoming_attr.setdefault(key, value)
    target_attr["source"] = _dedupe_source_records(
        [
            *(
                target_attr.get("source")
                if isinstance(target_attr.get("source"), list)
                else []
            ),
            *(
                incoming_attr.get("source")
                if isinstance(incoming_attr.get("source"), list)
                else _source_records_for_graph(incoming_attr)
            ),
        ]
    )
    for list_key in ("fields", "resolver_wrappers", "inputs", "outputs", "constraints"):
        target_attr[list_key] = _dedupe_strings(
            [*_string_values(target_attr.get(list_key)), *_string_values(incoming_attr.get(list_key))]
        )
    for key, value in incoming_attr.items():
        if key in {"source", "fields", "resolver_wrappers", "inputs", "outputs", "constraints"}:
            continue
        if value in ("", None, 0):
            continue
        existing = target_attr.get(key)
        if existing in ("", None, 0):
            target_attr[key] = value
        elif existing != value:
            conflicts = target_attr.setdefault("conflicts", {})
            if isinstance(conflicts, dict):
                values = conflicts.setdefault(key, [])
                if isinstance(values, list):
                    for candidate in (existing, value):
                        if candidate not in values:
                            values.append(candidate)
    if not target_attr.get("source"):
        target_attr["source"] = [_unknown_source_record()]
    target["attr"] = target_attr


def _merge_edge_attr_stats(stats: Dict[str, object], node: Mapping[str, object]) -> None:
    attr = node.get("attr") if isinstance(node.get("attr"), Mapping) else {}
    for field_name in _string_values(attr.get("fields")):
        stats["fields"].add(field_name)
    for wrapper in _string_values(attr.get("resolver_wrappers")):
        stats["resolver_wrappers"].add(wrapper)
    source_records = stats.get("source_records")
    if isinstance(source_records, list):
        source_records.extend(_source_records_for_graph(attr))


def _edge_attr_payload(stats: Mapping[str, object]) -> Dict[str, object]:
    payload = {
        "source": _dedupe_source_records(stats.get("source_records", []) if isinstance(stats.get("source_records"), list) else []),
        "fields": sorted(str(value) for value in stats.get("fields", set()) if value),
        "resolver_wrappers": sorted(str(value) for value in stats.get("resolver_wrappers", set()) if value),
    }
    original_relations = sorted(str(value) for value in stats.get("original_relations", set()) if value)
    if original_relations:
        payload["original_relation"] = original_relations[0] if len(original_relations) == 1 else original_relations
    return payload


def _append_boxmatrix_io(node_metadata: Dict[str, Dict[str, object]], edge: Mapping[str, object]) -> None:
    src = str(edge.get("src") or "")
    dst = str(edge.get("dst") or "")
    if not src or not dst:
        return
    src_meta = node_metadata.setdefault(src, _empty_boxmatrix_metadata(src, _kind_for_graph_symbol(src)))
    dst_meta = node_metadata.setdefault(dst, _empty_boxmatrix_metadata(dst, _kind_for_graph_symbol(dst)))
    src_label = str(src_meta.get("label") or _label_for_graph_node_id(src))
    dst_label = str(dst_meta.get("label") or _label_for_graph_node_id(dst))
    relation = str(edge.get("relation") or "related")
    edge_attr = edge.get("attr") if isinstance(edge.get("attr"), Mapping) else {}
    fields = _string_values(edge_attr.get("fields"))
    field_suffix = f".{','.join(fields)}" if fields else ""
    src_meta["out"] = _dedupe_strings([*_string_values(src_meta.get("out")), f"{relation} {dst_label}{field_suffix}"])
    dst_meta["in"] = _dedupe_strings([*_string_values(dst_meta.get("in")), f"{src_label} {relation}{field_suffix}"])


def _source_records_for_graph(metadata: Mapping[str, object]) -> List[Dict[str, object]]:
    raw_source = metadata.get("source")
    if isinstance(raw_source, list):
        return _dedupe_source_records(raw_source)
    record = {
        "corpus_id": str(metadata.get("corpus_id") or "unknown"),
        "repo": str(metadata.get("repo") or "unknown"),
        "path": str(metadata.get("path") or ""),
    }
    for key in ("line_start", "line_end", "page", "commit", "snippet_id"):
        value = metadata.get(key)
        if value not in ("", None, 0):
            record[key] = value
    return _dedupe_source_records([record])


def _dedupe_source_records(records: Iterable[object]) -> List[Dict[str, object]]:
    result: List[Dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            continue
        record = {
            "corpus_id": str(raw_record.get("corpus_id") or "unknown"),
            "repo": str(raw_record.get("repo") or "unknown"),
            "path": str(raw_record.get("path") or ""),
        }
        for key in ("line_start", "line_end", "page", "commit", "snippet_id"):
            value = raw_record.get(key)
            if value not in ("", None, 0):
                record[key] = value
        key = tuple(sorted(record.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    concrete = [
        record
        for record in result
        if any(str(record.get(key) or "") not in {"", "unknown"} for key in ("corpus_id", "repo", "path"))
    ]
    return concrete or result or [_unknown_source_record()]


def _unknown_source_record() -> Dict[str, object]:
    return {"corpus_id": "unknown", "repo": "unknown", "path": ""}


def _source_scope_for_graph(source: List[Mapping[str, object]]) -> str:
    if not source:
        return "unknown"
    first = source[0]
    return _slug_for_graph_heading(str(first.get("corpus_id") or first.get("repo") or "unknown"))


def _register_symbol_for_graph(symbol: str) -> str:
    cleaned = symbol.strip()
    for prefix in ("reg", "mm", "smn"):
        if cleaned.startswith(prefix) and len(cleaned) > len(prefix) and cleaned[len(prefix)].isupper():
            return cleaned[len(prefix) :]
    return cleaned


def _ip_for_graph_symbol(symbol: str, source: List[Mapping[str, object]]) -> str:
    text = f"{symbol} {' '.join(str(item.get('path') or '') for item in source)}".upper()
    for candidate in ("GC", "GMC", "CP", "SDMA", "BIF", "RLC", "GDS", "IH", "NBIO"):
        if candidate in text:
            return candidate
    return "unknown"


def _ip_version_for_graph_source(source: List[Mapping[str, object]]) -> str:
    text = " ".join(str(item.get("path") or "") for item in source)
    match = re.search(r"(?:v|_)(\d{1,2})[_\.-](\d)", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return "unknown"


def _language_for_graph_path(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith((".c", ".h")):
        return "c"
    if lowered.endswith((".cc", ".cpp", ".hpp")):
        return "cpp"
    if lowered.endswith(".py"):
        return "python"
    return "unknown"


def _looks_like_function_symbol(symbol: str) -> bool:
    if not symbol or "/" in symbol or "\\" in symbol or "." in Path(symbol).name:
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", symbol)) and not symbol.isupper()


def _snippet_has_callable_symbol(snippet: str, symbol: str) -> bool:
    if not snippet or not symbol:
        return False
    return bool(re.search(rf"\b{re.escape(symbol)}\s*\(", snippet))


def _merge_graph_metadata(base: Mapping[str, object], override: Optional[Mapping[str, object]]) -> Dict[str, object]:
    merged = dict(base)
    for key, value in dict(override or {}).items():
        if value not in ("", None, 0):
            merged[key] = value
    return merged


def _label_for_graph_node_id(node_id: str) -> str:
    if ":" in node_id:
        return node_id.rsplit(":", 1)[-1]
    return node_id


def _string_values(*values: object) -> List[str]:
    result: List[str] = []
    for value in values:
        if value in ("", None, 0):
            continue
        if isinstance(value, (list, tuple, set)):
            result.extend(str(item) for item in value if item not in ("", None, 0))
        else:
            result.append(str(value))
    return result


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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
    if _has_register_prefix_alias(symbol):
        return True
    return entity_type in {"register", "field", "macro", "context"} and len(symbol) > 3


def _normalize_graph_kind(kind: str) -> str:
    normalized = kind.lower()
    if normalized in {"function", "func"}:
        return "function"
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
    if normalized in {"doc_box", "box"}:
        return "doc_box"
    return "code"


def _normalize_graph_relation(relation: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", relation.lower()).strip("_")
    if normalized in {"read", "reads", "field_get", "field_read", "field_mask", "field_shift"}:
        return "reads"
    if normalized in {"write", "writes", "field_write", "field_value"}:
        return "writes"
    if normalized in {
        "field_set",
        "sets_field",
        "set_field",
        "sets_field_value",
        "reg_set_field",
        "read_modify_write",
        "read_modify_writes",
    }:
        return "sets_field"
    if normalized in {"maps_base", "map_base", "address", "offset", "maps_offset"}:
        return "maps_base"
    if normalized in {"calls", "call"}:
        return "calls"
    if normalized in {"contains", "contains_box"}:
        return "contains"
    if normalized in {"documents", "documents_register", "documented_by", "section_mentions", "explains"}:
        return "documents"
    if normalized in {"depends_on", "requires"}:
        return "depends_on"
    if normalized in {"configures", "programs"}:
        return "configures"
    if normalized in {"resets", "reset"}:
        return "resets"
    if normalized in {"wraps", "defined_in", "appears_in_code", "appears_in_doc", "appears_in_pdf", "has_field"}:
        return ""
    return "relates_to"


def _kind_for_graph_symbol(symbol: str) -> str:
    lowered = symbol.lower()
    path, anchor = _split_graph_section_symbol(symbol)
    if anchor.startswith("box-") and re.search(r"\.(?:md|rst|txt|pdf)$", path.lower()):
        return "doc_box"
    if re.search(r"\.(?:md|rst|txt)#", lowered):
        return "doc_section"
    if ".pdf#" in lowered:
        return "pdf_section"
    if lowered.endswith((".md", ".rst", ".txt")):
        return "doc"
    if lowered.endswith(".pdf"):
        return "pdf"
    if re.search(r"ENABLE|DISABLE|PENDING|MASK|SHIFT|RESET_REQUEST|INVALIDATE|FIELD", symbol):
        return "field"
    if _has_register_prefix_alias(symbol) or re.search(
        r"CNTL|STATUS|RESET|BASE|SIZE|VMID|DOORBELL|QUEUE|REGISTER",
        symbol,
    ):
        return "register"
    return "code"


def _has_register_prefix_alias(symbol: str) -> bool:
    return any(
        symbol.startswith(prefix) and len(symbol) > len(prefix) and symbol[len(prefix)].isupper()
        for prefix in ("reg", "mm", "smn")
    )


def _is_graph_wrapper_hub(symbol: str) -> bool:
    return is_resolver_wrapper_name(symbol)


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


def _section_metadata_for_graph_row(row: sqlite3.Row, section_id: str) -> Dict[str, object]:
    source_type = str(row["source_type"] or "")
    path = str(row["path"] or "").strip()
    heading = _first_markdown_heading(str(row["chunk_text"] or ""))
    page = int(row["page"] or 0) if "page" in row.keys() else 0
    line_start = int(row["line_start"] or 0) if "line_start" in row.keys() else 0
    anchor = _anchor_for_graph_symbol(section_id)
    metadata: Dict[str, object] = {
        "source_type": source_type,
        "path": path,
        "anchor": anchor,
        "label": _section_label_for_graph(path, source_type, anchor, heading, page, line_start),
    }
    if heading:
        metadata["heading"] = heading
    if page:
        metadata["page"] = page
    if line_start:
        metadata["line_start"] = line_start
    return metadata


def _metadata_for_graph_symbol(symbol: str) -> Dict[str, object]:
    kind = _kind_for_graph_symbol(symbol)
    if kind not in {"doc_section", "pdf_section", "doc", "pdf", "doc_box"}:
        return {}
    path, anchor = _split_graph_section_symbol(symbol)
    if not path:
        path = symbol
    source_type = "pdf" if path.lower().endswith(".pdf") else "doc"
    page_match = re.match(r"page-(\d+)$", anchor)
    page = int(page_match.group(1)) if page_match else 0
    metadata: Dict[str, object] = {
        "source_type": source_type,
        "path": path,
        "label": _section_label_for_graph(path, source_type, anchor, "", page, 0),
    }
    if anchor:
        metadata["anchor"] = anchor
    if page:
        metadata["page"] = page
    return metadata


def _metadata_from_networkx_edge_data(data: Mapping[str, object], endpoint: str) -> Dict[str, object]:
    try:
        provenance = json.loads(str(data.get("provenance_json") or "{}"))
    except json.JSONDecodeError:
        provenance = {}
    metadata = _metadata_for_graph_symbol(endpoint)
    metadata["path"] = str(data.get("path") or metadata.get("path") or "")
    for key in ("line_start", "line_end"):
        value = data.get(key)
        if value not in ("", None, 0):
            metadata[key] = value
    for key in (
        "corpus_id",
        "repo",
        "commit",
        "field",
        "fields",
        "function",
        "function_name",
        "ip",
        "ip_version",
        "language",
        "model",
        "provider",
        "resolver_wrappers",
        "wrapper",
        "job_id",
    ):
        value = provenance.get(key)
        if value not in ("", None, 0):
            metadata[key] = value
    _apply_endpoint_function_metadata(metadata, provenance, endpoint)
    metadata.setdefault("symbol", endpoint)
    return metadata


def _metadata_from_edge_provenance(row: sqlite3.Row, endpoint: str) -> Dict[str, object]:
    try:
        provenance = json.loads(str(row["provenance_json"] or "{}"))
    except json.JSONDecodeError:
        provenance = {}
    metadata = _metadata_for_graph_symbol(endpoint)
    metadata["path"] = str(row["path"] or metadata.get("path") or "")
    for key in ("line_start", "line_end"):
        value = row[key] if key in row.keys() else None
        if value not in ("", None, 0):
            metadata[key] = value
    for key in (
        "corpus_id",
        "repo",
        "commit",
        "field",
        "fields",
        "function",
        "function_name",
        "ip",
        "ip_version",
        "language",
        "model",
        "provider",
        "resolver_wrappers",
        "wrapper",
        "job_id",
    ):
        value = provenance.get(key)
        if value not in ("", None, 0):
            metadata[key] = value
    _apply_endpoint_function_metadata(metadata, provenance, endpoint)
    metadata.setdefault("symbol", endpoint)
    if str(provenance.get("extractor") or "") == "doc_nodes" and str(provenance.get("box_node_id") or "") == endpoint:
        box_name = str(provenance.get("box_name") or "").strip()
        if box_name:
            metadata["label"] = box_name
        summary = str(provenance.get("summary") or "").strip()
        if summary:
            metadata["summary"] = summary
        box_id = str(provenance.get("box_id") or "").strip()
        if box_id:
            metadata["box_id"] = box_id
        for key in ("inputs", "outputs", "constraints"):
            value = provenance.get(key)
            if isinstance(value, list):
                metadata[key] = value
        metadata["source_type"] = "pdf" if str(metadata.get("path") or "").lower().endswith(".pdf") else "doc"
    return metadata


def _apply_endpoint_function_metadata(
    metadata: Dict[str, object],
    provenance: Mapping[str, object],
    endpoint: str,
) -> None:
    if endpoint == str(provenance.get("function") or ""):
        metadata["function_name"] = endpoint
        return
    if endpoint != str(provenance.get("callee") or ""):
        return
    metadata["function_name"] = endpoint
    callback_path = str(provenance.get("callee_path") or provenance.get("callback_path") or "").strip()
    if callback_path:
        metadata["path"] = callback_path
    callback_line = provenance.get("callee_line") or provenance.get("callback_line")
    if callback_line not in ("", None, 0):
        metadata["line_start"] = callback_line
        metadata["line_end"] = callback_line


def _metadata_for_graph_evidence_row(row: sqlite3.Row, endpoint: str) -> Dict[str, object]:
    metadata: Dict[str, object] = {
        "path": str(row["path"] or ""),
        "line_start": row["line_start"],
        "page": row["page"] if "page" in row.keys() else None,
        "corpus_id": str(row["corpus_id"] or ""),
        "source_type": str(row["source_type"] or ""),
        "symbol": endpoint,
    }
    if _looks_like_function_symbol(endpoint):
        metadata["function_name"] = endpoint
    return {key: value for key, value in metadata.items() if value not in ("", None, 0)}


def _register_for_field_evidence_row(row: sqlite3.Row) -> str:
    text = f"{row['resolved_chain'] if 'resolved_chain' in row.keys() else ''} {row['snippet'] if 'snippet' in row.keys() else ''}"
    match = re.search(r"register\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    if match:
        return match.group(1)
    match = re.search(r"REG_SET_FIELD\s*\([^,]+,\s*([A-Za-z_][A-Za-z0-9_]*)\s*,", text)
    if match:
        return match.group(1)
    return ""


def _split_graph_section_symbol(symbol: str) -> tuple[str, str]:
    path, separator, anchor = symbol.partition("#")
    return (path, anchor) if separator else (symbol, "")


def _anchor_for_graph_symbol(symbol: str) -> str:
    return _split_graph_section_symbol(symbol)[1]


def _section_label_for_graph(
    path: str,
    source_type: str,
    anchor: str,
    heading: str,
    page: int,
    line_start: int,
) -> str:
    filename = Path(path).name if path else source_type or "section"
    if heading:
        return f"{filename} {heading}"
    if page:
        return f"{filename} page {page}"
    if anchor.startswith("lines-"):
        return f"{filename} line {anchor.removeprefix('lines-')}"
    if line_start:
        return f"{filename} line {line_start}"
    return f"{filename} {anchor}".strip()


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
    if relation in {"reads", "writes", "sets_field", "maps_base", "calls"}:
        return 0
    if relation in {"contains", "documents", "configures", "resets", "depends_on"}:
        return 1
    return 2


def _select_global_graph_edges(edges: List[Dict[str, object]], edge_limit: int) -> List[Dict[str, object]]:
    limit = max(0, int(edge_limit))
    if limit == 0:
        return []
    protected = [edge for edge in edges if _is_protected_global_edge(edge)]
    selected: List[Dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in [*protected, *edges]:
        key = (str(edge["src"]), str(edge["dst"]), str(edge["relation"]))
        if key in seen:
            continue
        seen.add(key)
        selected.append(edge)
        if len(selected) >= limit:
            break
    return selected


def _is_protected_global_edge(edge: Mapping[str, object]) -> bool:
    if str(edge.get("stage") or "") == "semantic":
        return True
    if str(edge.get("relation") or "") in {"contains_box", "section_mentions"}:
        return True
    return any(
        _kind_for_graph_symbol(str(edge.get(endpoint) or "")) in {"doc_box", "doc_section", "pdf_section"}
        for endpoint in ("src", "dst")
    )


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
        r"(?m)^\s*(?:static[ \t]+)?(?:inline[ \t]+)?(?:[A-Za-z_][\w \t\*]*[ \t]+)+(?P<name>[A-Za-z_]\w*)[ \t]*\([^\n;{}]*\)[ \t]*(?:\n[ \t]*)?\{"
    )
    ignored = {"if", "for", "while", "switch", "return", "sizeof"}
    matches = [match.group("name") for match in pattern.finditer(text)]
    for name in reversed(matches):
        if name not in ignored:
            return name
    return ""
