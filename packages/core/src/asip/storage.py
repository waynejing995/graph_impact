"""SQLite evidence storage and graph expansion utilities."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
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
        graph = self.to_networkx()
        edges = [
            {
                "src": src,
                "dst": dst,
                "relation": data["relation"],
                "confidence": float(data["confidence"]),
            }
            for src, dst, data in graph.edges(data=True)
        ]
        edges.sort(
            key=lambda edge: (-float(edge["confidence"]), str(edge["src"]), str(edge["dst"]), str(edge["relation"]))
        )
        selected_edges = edges[: max(0, limit)]
        node_weights: Dict[str, float] = {}
        for edge in selected_edges:
            confidence = float(edge["confidence"])
            node_weights[str(edge["src"])] = node_weights.get(str(edge["src"]), 0.0) + confidence
            node_weights[str(edge["dst"])] = node_weights.get(str(edge["dst"]), 0.0) + confidence
        nodes = [
            {"id": node, "weight": round(weight, 4)}
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
