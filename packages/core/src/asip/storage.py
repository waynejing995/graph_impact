"""SQLite evidence storage and graph expansion utilities."""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .graph_schema import normalize_product_relation
from .graph_filters import is_resolver_wrapper_name
from .resolver_profiles import (
    GraphFunctionNormalizationRule,
    GraphMergePolicy,
    GraphRegisterNormalization,
    load_resolver_profile,
    load_resolver_profiles,
    resolver_profile_from_config,
)


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

            create table if not exists job_events (
              id integer primary key,
              job_id integer not null references jobs(id),
              status text not null,
              message text not null default '',
              created_at text not null default current_timestamp
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
            create index if not exists idx_evidence_symbol_confidence
              on evidence(symbol, confidence desc, id asc);
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
        self._invalidate_runtime_graph_policy()

    def start_job(self, kind: str, message: str = "", metadata: Optional[Dict[str, object]] = None) -> int:
        cursor = self.con.execute(
            "insert into jobs(kind, status, message, metadata_json) values (?, 'queued', ?, ?)",
            (kind, message, json.dumps(metadata or {})),
        )
        job_id = int(cursor.lastrowid)
        self._append_job_event(job_id, "queued", message)
        self.con.commit()
        self._invalidate_runtime_graph_policy()
        return job_id

    def update_job_status(
        self,
        job_id: int,
        status: str,
        message: str = "",
        metadata: Optional[Dict[str, object]] = None,
    ) -> None:
        normalized_status = _normalize_job_status(status)
        current_row = self.con.execute(
            "select status, message from jobs where id = ?",
            (job_id,),
        ).fetchone()
        if current_row is None:
            raise KeyError(job_id)
        current_status = _normalize_job_status(str(current_row["status"] or ""))
        current_message = str(current_row["message"] or "")
        should_append_event = normalized_status != current_status or message != current_message
        current_metadata = self._job_metadata(job_id)
        current_metadata.update(metadata or {})
        self.con.execute(
            """
            update jobs
            set status = ?, message = ?, metadata_json = ?
            where id = ?
            """,
            (normalized_status, message, json.dumps(current_metadata), job_id),
        )
        if should_append_event:
            self._append_job_event(job_id, normalized_status, message)
        self.con.commit()
        self._invalidate_runtime_graph_policy()

    def finish_job(self, job_id: int, status: str, message: str = "") -> None:
        normalized_status = _normalize_job_status(status)
        metadata = self._job_metadata(job_id)
        if normalized_status == "succeeded" and status != "succeeded":
            metadata.setdefault("result_status", status)
        self.con.execute(
            """
            update jobs
            set status = ?, message = ?, metadata_json = ?, finished_at = current_timestamp
            where id = ?
            """,
            (normalized_status, message, json.dumps(metadata), job_id),
        )
        self._append_job_event(job_id, normalized_status, message)
        self.con.commit()
        self._invalidate_runtime_graph_policy()

    def get_job(self, job_id: int) -> Dict[str, object]:
        row = self.con.execute(
            "select id, kind, status, message, metadata_json, started_at, finished_at from jobs where id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._job_payload_from_row(row)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select id, kind, status, message, metadata_json, started_at, finished_at
            from jobs
            order by id desc
            limit ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        jobs: List[Dict[str, object]] = []
        for row in rows:
            jobs.append(self._job_payload_from_row(row))
        return jobs

    def _job_payload_from_row(self, row: sqlite3.Row) -> Dict[str, object]:
        result = dict(row)
        job_id = int(result["id"])
        raw_status = str(result.get("status") or "")
        normalized_status = _normalize_job_status(raw_status)
        metadata = json.loads(str(result.pop("metadata_json") or "{}"))
        if normalized_status == "succeeded" and raw_status.strip().lower() != "succeeded":
            metadata.setdefault("result_status", raw_status)
        result["status"] = normalized_status
        result["metadata"] = metadata
        events = self._job_events(job_id)
        if not events:
            events = [
                {
                    "id": 0,
                    "job_id": job_id,
                    "status": normalized_status,
                    "message": result.get("message") or "",
                    "created_at": result.get("finished_at") or result.get("started_at") or "",
                }
            ]
        else:
            events = [{**event, "status": _normalize_job_status(str(event.get("status") or ""))} for event in events]
        result["events"] = events
        return result

    def _append_job_event(self, job_id: int, status: str, message: str = "") -> None:
        self.con.execute(
            "insert into job_events(job_id, status, message) values (?, ?, ?)",
            (job_id, status, message),
        )

    def _job_events(self, job_id: int) -> List[Dict[str, object]]:
        rows = self.con.execute(
            """
            select id, job_id, status, message, created_at
            from job_events
            where job_id = ?
            order by id asc
            """,
            (job_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _job_metadata(self, job_id: int) -> Dict[str, object]:
        row = self.con.execute("select metadata_json from jobs where id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return json.loads(str(row["metadata_json"] or "{}"))

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
            selected_rows = list(chunk_rows)
            excluded_ids = [int(row["id"]) for row in selected_rows]
            symbol_rows = self._find_evidence_candidates_by_symbols(
                ranked_tokens,
                candidate_limit - len(selected_rows),
                exclude_ids=excluded_ids,
            )
            selected_rows.extend(symbol_rows)
            excluded_ids.extend(int(row["id"]) for row in symbol_rows)
            if len(selected_rows) >= candidate_limit or _tokens_look_like_exact_symbols(ranked_tokens):
                return selected_rows
            like_rows = self._find_evidence_candidates_by_like(
                ranked_tokens,
                candidate_limit - len(selected_rows),
                exclude_ids=excluded_ids,
            )
            return [*selected_rows, *like_rows]
        if not ranked_tokens:
            return self.all_evidence()
        symbol_rows = self._find_evidence_candidates_by_symbols(ranked_tokens, candidate_limit)
        if symbol_rows and _tokens_look_like_exact_symbols(ranked_tokens):
            return symbol_rows
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

    def _find_evidence_candidates_by_symbols(
        self,
        ranked_tokens: Iterable[str],
        limit: int,
        exclude_ids: Optional[Iterable[int]] = None,
    ) -> List[Dict[str, object]]:
        symbols = _symbol_aliases_for_query_tokens(ranked_tokens)
        if not symbols or limit <= 0:
            return []
        placeholders = ",".join("?" for _ in symbols)
        conditions = [f"symbol in ({placeholders})"]
        params: List[object] = list(symbols)
        excluded = list(dict.fromkeys(int(row_id) for row_id in (exclude_ids or [])))
        if excluded:
            excluded_placeholders = ",".join("?" for _ in excluded)
            conditions.append(f"id not in ({excluded_placeholders})")
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
        self.add_embeddings(
            [
                {
                    "chunk_id": chunk_id,
                    "provider": provider,
                    "model": model,
                    "vector": vector,
                    "metadata": metadata or {},
                }
            ]
        )

    def add_embeddings(self, rows: Iterable[Mapping[str, Any]]) -> None:
        prepared_rows = [
            (
                int(row["chunk_id"]),
                str(row["provider"]),
                str(row["model"]),
                json.dumps(list(row["vector"])),
                json.dumps(row.get("metadata") or {}),
            )
            for row in rows
        ]
        if not prepared_rows:
            return
        self.con.executemany(
            """
            insert into embeddings(chunk_id, provider, model, vector_json, metadata_json)
            values (?, ?, ?, ?, ?)
            on conflict(chunk_id) do update set
              provider=excluded.provider,
              model=excluded.model,
              vector_json=excluded.vector_json,
              metadata_json=excluded.metadata_json
            """,
            prepared_rows,
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

    def _graph_function_normalization_rules_by_profile(self) -> Dict[str, tuple[GraphFunctionNormalizationRule, ...]]:
        rows = self.list_resolver_profiles() if self._table_exists("resolver_profiles") else []
        rules_by_profile: Dict[str, tuple[GraphFunctionNormalizationRule, ...]] = dict(
            _default_function_normalization_rules_by_profile()
        )
        for row in rows:
            profile_id = str(row.get("id") or "")
            if not profile_id:
                continue
            profile = _resolver_profile_from_graph_row(row)
            aliases = _resolver_profile_aliases_for_graph_row(row, profile)
            if not row.get("enabled", True):
                for alias in aliases:
                    rules_by_profile[alias] = ()
                continue
            rules: tuple[GraphFunctionNormalizationRule, ...] = ()
            if profile is not None and profile.graph.function_normalization.enabled:
                rules = tuple(rule for rule in profile.graph.function_normalization.rules if rule.enabled)
            for alias in aliases:
                rules_by_profile[alias] = rules
        return rules_by_profile

    def _graph_register_normalization_by_profile(self) -> Dict[str, GraphRegisterNormalization]:
        rows = self.list_resolver_profiles() if self._table_exists("resolver_profiles") else []
        normalization_by_profile: Dict[str, GraphRegisterNormalization] = dict(
            _default_register_normalization_by_profile()
        )
        for row in rows:
            profile_id = str(row.get("id") or "")
            if not profile_id:
                continue
            profile = _resolver_profile_from_graph_row(row)
            aliases = _resolver_profile_aliases_for_graph_row(row, profile)
            if not row.get("enabled", True):
                for alias in aliases:
                    normalization_by_profile[alias] = GraphRegisterNormalization()
                continue
            normalization = profile.graph.register_normalization if profile is not None else GraphRegisterNormalization()
            for alias in aliases:
                normalization_by_profile[alias] = normalization
        return normalization_by_profile

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
        self._invalidate_runtime_graph_policy()

    def load_provider_settings(self, settings_id: str = "default") -> Dict[str, object]:
        row = self.con.execute("select settings_json from provider_settings where id = ?", (settings_id,)).fetchone()
        if row is None:
            return {}
        return json.loads(str(row["settings_json"]))

    def search_vector(
        self,
        vector: List[float],
        limit: int,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        filters = []
        params: List[object] = []
        if provider:
            filters.append("embeddings.provider = ?")
            params.append(provider)
        if model:
            filters.append("embeddings.model = ?")
            params.append(model)
        where_clause = f"where {' and '.join(filters)}" if filters else ""
        rows = [
            dict(row)
            for row in self.con.execute(
                f"""
                select
                  embeddings.chunk_id,
                  embeddings.provider,
                  embeddings.model,
                  embeddings.vector_json,
                  embeddings.metadata_json,
                  chunks.text,
                  documents.path
                from embeddings
                join chunks on chunks.id = embeddings.chunk_id
                join documents on documents.id = chunks.document_id
                {where_clause}
                """,
                params,
            )
        ]
        native_matches = self._search_vector_sqlite_vec(vector, limit, rows)
        if native_matches is not None:
            return native_matches
        return self._search_vector_python(vector, limit, rows)

    def _search_vector_python(
        self,
        vector: List[float],
        limit: int,
        rows: Iterable[Mapping[str, object]],
    ) -> List[Dict[str, object]]:
        scored = []
        for row in rows:
            stored_vector = json.loads(str(row["vector_json"]))
            scored.append(
                {
                    "chunk_id": int(row["chunk_id"]),
                    "provider": row["provider"],
                    "model": row["model"],
                    "metadata_json": row.get("metadata_json", "{}"),
                    "text": row["text"],
                    "path": row["path"],
                    "score": _cosine_similarity(vector, stored_vector),
                    "retrieval_runtime": "python-cosine",
                }
            )
        return sorted(scored, key=lambda item: float(item["score"]), reverse=True)[:limit]

    def _search_vector_sqlite_vec(
        self,
        vector: List[float],
        limit: int,
        rows: List[Mapping[str, object]],
    ) -> Optional[List[Dict[str, object]]]:
        if not vector or not rows or importlib.util.find_spec("sqlite_vec") is None:
            return None
        if not hasattr(self.con, "enable_load_extension"):
            return None
        dimension = len(vector)
        prepared: List[tuple[int, Mapping[str, object], List[float]]] = []
        for row in rows:
            try:
                stored_vector = [float(value) for value in json.loads(str(row["vector_json"]))]
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if len(stored_vector) != dimension:
                continue
            prepared.append((int(row["chunk_id"]), row, stored_vector))
        if not prepared:
            return None
        try:
            import sqlite_vec  # type: ignore[import-not-found]

            self.con.enable_load_extension(True)
            sqlite_vec.load(self.con)
            self.con.enable_load_extension(False)
            self.con.execute("drop table if exists temp.asip_vec_search")
            self.con.execute(f"create virtual table temp.asip_vec_search using vec0(embedding float[{dimension}])")
            self.con.executemany(
                "insert into temp.asip_vec_search(rowid, embedding) values (?, ?)",
                [
                    (chunk_id, sqlite_vec.serialize_float32(stored_vector))
                    for chunk_id, _row, stored_vector in prepared
                ],
            )
            native_rows = list(
                self.con.execute(
                    """
                    select rowid, distance
                    from asip_vec_search
                    where embedding match ?
                    order by distance
                    limit ?
                    """,
                    (sqlite_vec.serialize_float32([float(value) for value in vector]), max(1, int(limit))),
                )
            )
        except Exception:
            try:
                self.con.enable_load_extension(False)
            except Exception:
                pass
            try:
                self.con.execute("drop table if exists temp.asip_vec_search")
            except Exception:
                pass
            return None
        finally:
            try:
                self.con.enable_load_extension(False)
            except Exception:
                pass
        by_chunk = {chunk_id: (row, stored_vector) for chunk_id, row, stored_vector in prepared}
        scored = []
        for native_row in native_rows:
            chunk_id = int(native_row["rowid"])
            row, stored_vector = by_chunk[chunk_id]
            scored.append(
                {
                    "chunk_id": chunk_id,
                    "provider": row["provider"],
                    "model": row["model"],
                    "metadata_json": row.get("metadata_json", "{}"),
                    "text": row["text"],
                    "path": row["path"],
                    "score": _cosine_similarity(vector, stored_vector),
                    "distance": float(native_row["distance"]),
                    "retrieval_runtime": "sqlite-vec",
                }
            )
        try:
            self.con.execute("drop table if exists temp.asip_vec_search")
        except Exception:
            pass
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
            rows = self._runtime_graph_edge_rows(
                f"""
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

    def _runtime_graph_edge_rows(
        self,
        tail_sql: str = "",
        params: Iterable[object] = (),
        include_evidence_derived: bool = False,
    ) -> List[sqlite3.Row]:
        rows = self.con.execute(
            f"""
                select id, src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json
                from edges
                {tail_sql}
                """,
            tuple(params),
        )
        return [
            row
            for row in rows
            if self._runtime_graph_edge_row_is_usable(row, include_evidence_derived=include_evidence_derived)
        ]

    def _runtime_graph_edge_row_is_usable(self, row: sqlite3.Row, include_evidence_derived: bool = False) -> bool:
        stage = str(row["stage"] or "deterministic")
        if stage == "evidence" and not include_evidence_derived:
            return False
        if stage != "semantic":
            return True
        policy = self._runtime_semantic_graph_policy()
        try:
            provenance = json.loads(str(row["provenance_json"] or "{}"))
        except json.JSONDecodeError:
            provenance = {}
        extractor = str(provenance.get("extractor") or "")
        if not policy["enforce_job_provenance"] and extractor not in {"semantic_edges", "doc_nodes"}:
            return True
        job_id = _int_graph_value(provenance.get("job_id"))
        if not job_id:
            return False
        valid_job_ids_by_extractor = policy.get("valid_job_ids_by_extractor")
        if isinstance(valid_job_ids_by_extractor, Mapping):
            valid_extractor_job_ids = valid_job_ids_by_extractor.get(extractor)
            if not isinstance(valid_extractor_job_ids, set) or job_id not in valid_extractor_job_ids:
                return False
        elif job_id not in policy["valid_job_ids"]:
            return False
        expected_provider = str(policy.get("expected_provider") or "")
        expected_model = str(policy.get("expected_model") or "")
        provider = str(provenance.get("provider") or row["source"] or "").strip()
        model = str(provenance.get("model") or "").strip()
        if expected_provider and provider != expected_provider:
            return False
        if expected_model and model != expected_model:
            return False
        freshness_floor = policy["freshness_floor_job_id"]
        if freshness_floor is not None and job_id < int(freshness_floor):
            return False
        return True

    def _runtime_semantic_graph_policy(self) -> Dict[str, object]:
        cached = getattr(self, "_runtime_semantic_graph_policy_cache", None)
        if isinstance(cached, dict):
            return cached
        policy: Dict[str, object] = {
            "enforce_job_provenance": False,
            "freshness_floor_job_id": None,
            "valid_job_ids": set(),
            "valid_job_ids_by_extractor": {"semantic_edges": set(), "doc_nodes": set()},
            "expected_provider": "",
            "expected_model": "",
        }
        if not self._table_exists("jobs"):
            self._runtime_semantic_graph_policy_cache = policy
            return policy
        expected_provider = ""
        expected_model = ""
        if self._table_exists("provider_settings"):
            try:
                settings = self.load_provider_settings()
            except Exception:
                settings = {}
            edge_settings = settings.get("edge") if isinstance(settings, Mapping) else None
            if isinstance(edge_settings, Mapping):
                expected_provider = str(edge_settings.get("provider") or "ollama").strip()
                expected_model = str(edge_settings.get("model") or edge_settings.get("preferred") or "").strip()
        latest_index_job_id: Optional[int] = None
        latest_graph_rebuild_job_id: Optional[int] = None
        has_semantic_jobs = False
        valid_job_ids: set[int] = set()
        valid_job_ids_by_extractor: Dict[str, set[int]] = {"semantic_edges": set(), "doc_nodes": set()}
        rows = self.con.execute("select id, kind, status, metadata_json from jobs order by id asc")
        for row in rows:
            job_id = _int_graph_value(row["id"])
            if not job_id:
                continue
            kind = str(row["kind"] or "")
            status = _normalize_job_status(str(row["status"] or ""))
            if status != "succeeded":
                continue
            if kind == "index":
                latest_index_job_id = max(latest_index_job_id or job_id, job_id)
                continue
            if kind == "graph_rebuild":
                latest_graph_rebuild_job_id = max(latest_graph_rebuild_job_id or job_id, job_id)
                continue
            if kind not in {"semantic_edges", "semantic_edges_batch", "doc_nodes_batch"}:
                continue
            has_semantic_jobs = True
            if not _semantic_graph_job_matches_provider(row, expected_provider, expected_model):
                continue
            valid_job_ids.add(job_id)
            if kind in {"semantic_edges", "semantic_edges_batch"}:
                valid_job_ids_by_extractor["semantic_edges"].add(job_id)
            elif kind == "doc_nodes_batch":
                valid_job_ids_by_extractor["doc_nodes"].add(job_id)
        freshness_floor_job_id = max(
            [job_id for job_id in (latest_index_job_id, latest_graph_rebuild_job_id) if job_id is not None],
            default=None,
        )
        policy = {
            "enforce_job_provenance": bool(has_semantic_jobs or freshness_floor_job_id is not None),
            "freshness_floor_job_id": freshness_floor_job_id,
            "valid_job_ids": valid_job_ids,
            "valid_job_ids_by_extractor": valid_job_ids_by_extractor,
            "expected_provider": expected_provider,
            "expected_model": expected_model,
        }
        self._runtime_semantic_graph_policy_cache = policy
        return policy

    def _invalidate_runtime_graph_policy(self) -> None:
        if hasattr(self, "_runtime_semantic_graph_policy_cache"):
            delattr(self, "_runtime_semantic_graph_policy_cache")

    def expand_graph_networkx(
        self,
        symbol: str,
        hops: int = 1,
        include_evidence_derived: bool = False,
        function_view: str = "concept",
    ) -> Dict[str, object]:
        return self.expand_graph_networkx_many(
            [symbol],
            hops=hops,
            include_evidence_derived=include_evidence_derived,
            function_view=function_view,
        )

    def expand_graph_networkx_many(
        self,
        symbols: Iterable[str],
        hops: int = 1,
        include_evidence_derived: bool = False,
        function_view: str = "concept",
    ) -> Dict[str, object]:
        seed_symbols = [str(symbol) for symbol in symbols if str(symbol)]
        seed_symbols = [symbol for symbol in seed_symbols if not _is_graph_wrapper_hub(symbol)]
        if not seed_symbols:
            return {"nodes": [], "edges": [], "graph_runtime": "networkx"}
        if not self._has_expandable_edges(include_evidence_derived=include_evidence_derived):
            return _multi_seed_graph(seed_symbols)
        if not include_evidence_derived:
            return self._expand_graph_networkx_many_by_frontier(
                seed_symbols,
                hops=hops,
                function_view=function_view,
            )
        graph = self.to_networkx(include_evidence_derived=include_evidence_derived)
        seen = set(seed_symbols)
        frontier = set(seed_symbols)

        for _ in range(max(1, hops)):
            next_frontier = set()
            for node in frontier:
                if node not in graph:
                    continue
                if node not in seed_symbols and _is_graph_wrapper_hub(str(node)):
                    continue
                neighbors = set(graph.successors(node)) | set(graph.predecessors(node))
                next_frontier.update(neighbor for neighbor in neighbors if neighbor not in seen)
            if not next_frontier:
                break
            seen.update(next_frontier)
            frontier = next_frontier

        return self._networkx_subgraph_payload(graph, seen, seed_symbols, function_view=function_view)

    def _expand_graph_networkx_many_by_frontier(
        self,
        seed_symbols: Iterable[str],
        hops: int = 1,
        function_view: str = "concept",
    ) -> Dict[str, object]:
        import networkx as nx

        seeds = [str(symbol) for symbol in seed_symbols if str(symbol)]
        seen = set(seeds)
        frontier = set(seeds)
        selected_rows: Dict[int, sqlite3.Row] = {}
        graph = nx.MultiDiGraph()

        for _ in range(max(1, hops)):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self._runtime_graph_edge_rows(
                f"""
                where stage <> 'evidence'
                  and (src in ({placeholders}) or dst in ({placeholders}))
                order by confidence desc, id asc
                """,
                tuple(frontier) + tuple(frontier),
            )
            next_frontier = set()
            for row in rows:
                src = str(row["src"])
                dst = str(row["dst"])
                if _is_graph_wrapper_hub(src) or _is_graph_wrapper_hub(dst):
                    continue
                selected_rows[int(row["id"])] = row
                for endpoint in (src, dst):
                    if endpoint not in seen:
                        seen.add(endpoint)
                        next_frontier.add(endpoint)
            frontier = next_frontier

        for row in selected_rows.values():
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
        return self._networkx_subgraph_payload(graph, seen, seeds, function_view=function_view)

    def _networkx_subgraph_payload(
        self,
        graph: object,
        seen: set[str],
        fallback_symbols: Iterable[str],
        function_view: str = "concept",
    ) -> Dict[str, object]:
        subgraph = graph.subgraph(seen)
        subgraph_edges = list(subgraph.edges(data=True))
        has_semantic_edges = any(str(data.get("stage") or "") == "semantic" for _src, _dst, data in subgraph_edges)
        edges = []
        node_ids = set()
        node_payloads: Dict[str, Dict[str, object]] = {}
        known_function_metadata = self._known_graph_function_metadata() if has_semantic_edges else {}
        known_function_symbols = set(known_function_metadata)
        function_rules_by_profile = self._graph_function_normalization_rules_by_profile()
        register_normalization_by_profile = self._graph_register_normalization_by_profile()

        def remember_payload(node_id: str, kind: str, node: Mapping[str, object]) -> None:
            node_ids.add(node_id)
            payload = _boxmatrix_node_payload(node_id, kind, 1, node)
            existing = node_payloads.get(node_id)
            if existing is not None:
                _merge_boxmatrix_metadata(existing, payload)
                existing["weight"] = round(float(existing.get("weight") or 1.0) + 1.0, 4)
                return
            node_payloads[node_id] = payload

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
                function_view=function_view,
                function_rules_by_profile=function_rules_by_profile,
                register_normalization_by_profile=register_normalization_by_profile,
            )
            dst_node = _product_graph_node(
                str(dst),
                _kind_for_graph_symbol(str(dst)),
                dst_metadata,
                known_function_symbols=semantic_functions,
                function_view=function_view,
                function_rules_by_profile=function_rules_by_profile,
                register_normalization_by_profile=register_normalization_by_profile,
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
            resolver_profile_ids = _dedupe_strings(
                [
                    *_resolver_profile_ids_for_graph(src_metadata),
                    *_resolver_profile_ids_for_graph(dst_metadata),
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
                    "resolver_profile_ids": resolver_profile_ids,
                    "resolver_wrappers": resolver_wrappers,
                    "implementations": _dedupe_mapping_records(
                        [
                            *(
                                src_node.get("attr", {}).get("raw_implementations", [])
                                if isinstance(src_node.get("attr"), Mapping)
                                and isinstance(src_node.get("attr", {}).get("raw_implementations"), list)
                                else []
                            ),
                            *(
                                dst_node.get("attr", {}).get("raw_implementations", [])
                                if isinstance(dst_node.get("attr"), Mapping)
                                and isinstance(dst_node.get("attr", {}).get("raw_implementations"), list)
                                else []
                            ),
                        ]
                    ),
                },
            }
            _apply_callback_dispatch_edge_attr(edge["attr"], src_metadata, dst_metadata)
            original_relations = _original_relations_for_graph_edge(
                relation,
                str(data["relation"]),
                src_metadata,
                dst_metadata,
            )
            if original_relations:
                edge["attr"]["original_relation"] = (
                    original_relations[0] if len(original_relations) == 1 else original_relations
                )
            edges.append(edge)
            remember_payload(edge["src"], str(src_node["kind"]), src_node)
            remember_payload(edge["dst"], str(dst_node["kind"]), dst_node)
        if not node_ids:
            for symbol in fallback_symbols:
                seed_node = _product_graph_node(
                    symbol,
                    _kind_for_graph_symbol(symbol),
                    {},
                    function_view=function_view,
                    function_rules_by_profile=function_rules_by_profile,
                    register_normalization_by_profile=register_normalization_by_profile,
                )
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
        function_view: str = "concept",
        compact: bool = False,
    ) -> Dict[str, object]:
        edge_limit = None if limit is None else max(0, int(limit))
        evidence_cap = 0 if evidence_row_cap is None else max(0, int(evidence_row_cap))
        cooccurrence_limit = None if cooccurrence_symbol_limit is None else max(0, int(cooccurrence_symbol_limit))
        edge_stats: Dict[tuple[str, str, str], Dict[str, object]] = {}
        node_kinds: Dict[str, str] = {}
        node_metadata: Dict[str, Dict[str, object]] = {}
        known_function_metadata: Optional[Dict[str, Dict[str, object]]] = None
        known_function_symbols: Optional[set[str]] = None
        function_rules_by_profile = self._graph_function_normalization_rules_by_profile()
        register_normalization_by_profile = self._graph_register_normalization_by_profile()

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
            if stage == "semantic" and not compact:
                semantic_metadata, semantic_symbols = semantic_function_metadata()
                src_metadata = _merge_graph_metadata(semantic_metadata.get(src, {}), src_metadata)
                dst_metadata = _merge_graph_metadata(semantic_metadata.get(dst, {}), dst_metadata)
                semantic_functions = semantic_symbols
            else:
                semantic_functions = None
            src_node = _product_graph_node(
                src,
                src_kind,
                src_metadata,
                known_function_symbols=semantic_functions,
                function_view=function_view,
                function_rules_by_profile=function_rules_by_profile,
                register_normalization_by_profile=register_normalization_by_profile,
            )
            dst_node = _product_graph_node(
                dst,
                dst_kind,
                dst_metadata,
                known_function_symbols=semantic_functions,
                function_view=function_view,
                function_rules_by_profile=function_rules_by_profile,
                register_normalization_by_profile=register_normalization_by_profile,
            )
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
                    "providers": set(),
                    "models": set(),
                    "job_ids": set(),
                    "resolver_profile_ids": set(),
                    "resolver_wrappers": set(),
                    "original_relations": set(),
                    "dispatch_scopes": set(),
                    "call_kinds": set(),
                    "callback_candidate_counts": set(),
                    "callback_ambiguous": False,
                    "source_records": [],
                    "raw_implementations": [],
                    "src_nodes": [],
                    "dst_nodes": [],
                },
            )
            stats["confidence_sum"] = float(stats["confidence_sum"]) + bounded_confidence
            stats["count"] = int(stats["count"]) + 1
            stats["stages"].add(stage or "deterministic")
            if source:
                stats["sources"].add(source)
            for raw_relation in _original_relations_for_graph_edge(
                relation,
                original_relation,
                src_metadata or {},
                dst_metadata or {},
            ):
                stats["original_relations"].add(raw_relation)
            _merge_edge_attr_stats(stats, src_node)
            _merge_edge_attr_stats(stats, dst_node)
            _merge_callback_dispatch_stats(stats, src_metadata or {}, dst_metadata or {})
            if compact:
                node_kinds.setdefault(src, str(src_node.get("kind") or src_kind))
                node_kinds.setdefault(dst, str(dst_node.get("kind") or dst_kind))
                _remember_compact_graph_node(node_metadata, src_node)
                _remember_compact_graph_node(node_metadata, dst_node)
            else:
                stats["src_nodes"].append(src_node)
                stats["dst_nodes"].append(dst_node)

        had_persisted_graph_rows = False
        for row in self._runtime_graph_edge_rows(include_evidence_derived=include_evidence_derived):
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
            stats = edge_stats.get((str(edge["src"]), str(edge["dst"]), str(edge["relation"])), {})
            weight = float(edge["weight"])
            node_weights[str(edge["src"])] = node_weights.get(str(edge["src"]), 0.0) + weight
            node_weights[str(edge["dst"])] = node_weights.get(str(edge["dst"]), 0.0) + weight
            if not compact:
                for node in [
                    *(stats.get("src_nodes") if isinstance(stats.get("src_nodes"), list) else []),
                    *(stats.get("dst_nodes") if isinstance(stats.get("dst_nodes"), list) else []),
                ]:
                    if isinstance(node, Mapping):
                        remember_node(node)
                _append_boxmatrix_io(node_metadata, edge)
        _mark_function_concept_divergence(node_metadata, selected_edges, function_rules_by_profile)
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
        tail_sql = "" if include_evidence_derived else "where stage <> 'evidence'"
        return any(self._runtime_graph_edge_rows(tail_sql, include_evidence_derived=include_evidence_derived))

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
        for row in self._runtime_graph_edge_rows(include_evidence_derived=include_evidence_derived):
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


def section_overlay_graph_for_evidence_rows(rows: Iterable[Mapping[str, object]]) -> Dict[str, object]:
    node_payloads: Dict[str, Dict[str, object]] = {}
    edges: Dict[tuple[str, str, str], Dict[str, object]] = {}

    def remember(node: Mapping[str, object], weight: float = 1.0) -> None:
        node_id = str(node.get("id") or "")
        if not node_id:
            return
        existing = node_payloads.get(node_id)
        payload = _boxmatrix_node_payload(
            node_id,
            str(node.get("kind") or _kind_for_graph_symbol(node_id)),
            weight,
            node,
        )
        if existing is not None:
            _merge_boxmatrix_metadata(existing, payload)
            existing["weight"] = round(float(existing.get("weight") or 1.0) + weight, 4)
            return
        node_payloads[node_id] = payload

    for row in rows:
        source_type = str(row.get("source_type") or row.get("source") or "").strip().lower()
        if source_type not in {"doc", "pdf"}:
            continue
        path = str(row.get("path") or "").strip()
        if not path:
            continue
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            continue
        section_id, section_kind, section_metadata = _section_node_for_graph_mapping(row)
        if not section_id:
            continue
        section_node = _product_graph_node(section_id, section_kind, section_metadata)
        if section_node is None:
            continue
        confidence = max(0.05, min(1.0, float(row.get("confidence") or 0.5)))
        remember(section_node, confidence)

        symbol_kind = _kind_for_graph_evidence(
            source_type,
            str(row.get("entity_type") or ""),
            symbol,
        )
        symbol_metadata = _metadata_for_graph_mapping(row, symbol)
        symbol_node = _product_graph_node(symbol, symbol_kind, symbol_metadata)
        relation = _normalize_graph_relation("section_mentions")
        if symbol_node is None or not relation:
            continue
        remember(symbol_node, confidence)
        edge = {
            "src": str(section_node["id"]),
            "dst": str(symbol_node["id"]),
            "relation": relation,
            "confidence": round(confidence * 0.92, 4),
            "stage": "evidence",
            "source": "query_matched_section",
            "attr": {
                "source": _dedupe_source_records(
                    [
                        *_source_records_for_graph(section_metadata),
                        *_source_records_for_graph(symbol_metadata),
                    ]
                ),
                "fields": [],
                "resolver_wrappers": [],
            },
        }
        edges[(str(edge["src"]), str(edge["relation"]), str(edge["dst"]))] = edge

    return {
        "nodes": [node_payloads[node] for node in sorted(node_payloads)],
        "edges": sorted(
            edges.values(),
            key=lambda edge: (-float(edge["confidence"]), str(edge["src"]), str(edge["dst"]), str(edge["relation"])),
        ),
        "graph_runtime": "networkx",
    }


def _product_graph_node(
    symbol: str,
    kind: str,
    metadata: Optional[Mapping[str, object]] = None,
    known_function_symbols: Optional[set[str]] = None,
    function_view: str = "concept",
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
    register_normalization_by_profile: Optional[Mapping[str, GraphRegisterNormalization]] = None,
) -> Optional[Dict[str, object]]:
    raw_metadata: Dict[str, object] = dict(metadata or {})
    if not raw_metadata:
        raw_metadata.update(_metadata_for_graph_symbol(symbol))
    normalized_kind = _normalize_graph_kind(kind)
    function_name = str(raw_metadata.get("function_name") or "").strip()
    if not function_name and symbol == str(raw_metadata.get("function") or ""):
        function_name = symbol
    if function_name:
        return _function_graph_node(
            symbol,
            function_name,
            raw_metadata,
            function_view=function_view,
            function_rules_by_profile=function_rules_by_profile,
        )
    if normalized_kind in {"field", "doc", "pdf"}:
        return None
    if normalized_kind == "register":
        return _register_graph_node(
            symbol,
            raw_metadata,
            register_normalization_by_profile=register_normalization_by_profile,
        )
    if normalized_kind in {"doc_section", "pdf_section", "doc_box"}:
        return _document_graph_node(symbol, normalized_kind, raw_metadata)
    if not function_name and _looks_like_function_symbol(symbol) and (
        known_function_symbols is None or symbol in known_function_symbols
    ):
        function_name = symbol
    if function_name:
        return _function_graph_node(
            symbol,
            function_name,
            raw_metadata,
            function_view=function_view,
            function_rules_by_profile=function_rules_by_profile,
        )
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


def _multi_seed_graph(symbols: Iterable[str]) -> Dict[str, object]:
    node_payloads: Dict[str, Dict[str, object]] = {}
    for symbol in symbols:
        seed_node = _product_graph_node(str(symbol), _kind_for_graph_symbol(str(symbol)), {})
        if seed_node is None:
            continue
        node_payloads[str(seed_node["id"])] = _boxmatrix_node_payload(
            str(seed_node["id"]),
            str(seed_node["kind"]),
            1,
            seed_node,
        )
    return {
        "nodes": [node_payloads[node_id] for node_id in sorted(node_payloads)],
        "edges": [],
        "graph_runtime": "networkx",
    }


def _register_graph_node(
    symbol: str,
    metadata: Mapping[str, object],
    register_normalization_by_profile: Optional[Mapping[str, GraphRegisterNormalization]] = None,
) -> Dict[str, object]:
    register_symbol = _register_symbol_for_graph(str(metadata.get("symbol") or symbol))
    source = _source_records_for_graph(metadata)
    ip = str(metadata.get("ip") or _ip_for_graph_symbol(register_symbol, source) or "unknown")
    ip_version = str(metadata.get("ip_version") or _ip_version_for_graph_source(source) or "unknown")
    register_normalization = _register_normalization_for_metadata(metadata, register_normalization_by_profile)
    node_id = _register_node_id_for_graph(register_symbol, ip, ip_version, register_normalization)
    ip_versions = _dedupe_strings(
        [
            *_string_values(metadata.get("ip_versions")),
            *[str(item.get("ip_version") or "") for item in source if isinstance(item, Mapping)],
            ip_version,
        ]
    )
    attr = {
        "source": source,
        "symbol": register_symbol,
        "ip": ip,
        "ip_version": ip_version,
        "ip_versions": ip_versions,
        "fields": _string_values(metadata.get("fields"), metadata.get("field")),
        "resolver_wrappers": _string_values(metadata.get("resolver_wrappers"), metadata.get("wrapper")),
    }
    attr.update(_provider_metadata_for_graph(metadata))
    return {"id": node_id, "kind": "register", "label": register_symbol, "attr": attr, "in": [], "out": []}


def _function_graph_node(
    symbol: str,
    function_name: str,
    metadata: Mapping[str, object],
    function_view: str = "concept",
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
) -> Dict[str, object]:
    source = _source_records_for_graph(metadata)
    primary_source = source[0]
    path = str(primary_source.get("path") or str(metadata.get("path") or "unknown"))
    scope = _source_scope_for_graph(source)
    concept = _function_concept_for_graph(
        function_name,
        metadata,
        function_view,
        function_rules_by_profile=function_rules_by_profile,
    )
    canonical_function_name = concept.get("function_name", function_name)
    if concept.get("rule_id"):
        node_id = (
            f"function:{scope}:concept:{concept.get('profile_id') or 'unknown'}:"
            f"{concept['rule_id']}:{canonical_function_name}"
        )
    else:
        node_id = f"function:{scope}:{path}:{function_name}"
    raw_implementation = _function_raw_implementation(function_name, path, metadata, source)
    attr = {
        "source": source,
        "function_name": canonical_function_name,
        "raw_function_names": [function_name],
        "raw_implementations": [raw_implementation],
        "language": str(metadata.get("language") or _language_for_graph_path(path)),
        "fields": _string_values(metadata.get("fields"), metadata.get("field")),
        "resolver_wrappers": _string_values(metadata.get("resolver_wrappers"), metadata.get("wrapper")),
    }
    attr.update(_provider_metadata_for_graph(metadata))
    for key in ("ip_block", "ip_version"):
        if concept.get(key) not in ("", None, 0):
            attr[key] = concept[key]
    if concept.get("rule_id"):
        attr["normalization_rule"] = concept["rule_id"]
        attr["normalization_profile_id"] = concept.get("profile_id") or "unknown"
        attr["merge_status"] = "merged"
    resolver_profile_ids = _resolver_profile_ids_for_graph(metadata)
    if resolver_profile_ids:
        attr["resolver_profile_ids"] = resolver_profile_ids
    return {"id": node_id, "kind": "function", "label": canonical_function_name, "attr": attr, "in": [], "out": []}


def _document_graph_node(symbol: str, kind: str, metadata: Mapping[str, object]) -> Dict[str, object]:
    source = _source_records_for_graph(metadata)
    doc_kind = {
        "doc_section": "markdown_section",
        "pdf_section": "pdf_section",
        "doc_box": "boxmatrix_box",
    }.get(kind, kind or "doc")
    attr = {
        "source": source,
        "doc_kind": doc_kind,
        "anchor": str(metadata.get("anchor") or _anchor_for_graph_symbol(symbol)),
        "summary": str(metadata.get("summary") or ""),
        "fields": _string_values(metadata.get("fields"), metadata.get("field")),
        "resolver_wrappers": _string_values(metadata.get("resolver_wrappers"), metadata.get("wrapper")),
    }
    attr.update(_provider_metadata_for_graph(metadata))
    page = _doc_page_for_graph(metadata, str(attr["anchor"]))
    if page:
        attr["page"] = page
    if kind == "doc_box":
        attr["box_id"] = str(metadata.get("box_id") or attr["anchor"] or Path(str(metadata.get("path") or symbol)).name)
        attr["inputs"] = _string_values(metadata.get("inputs"))
        attr["outputs"] = _string_values(metadata.get("outputs"))
        attr["constraints"] = _string_values(metadata.get("constraints"))
    else:
        attr["section_id"] = str(metadata.get("section_id") or attr["anchor"] or symbol)
        attr["title"] = str(metadata.get("title") or metadata.get("heading") or metadata.get("label") or Path(symbol).name)
    label = str(metadata.get("label") or attr.get("title") or attr.get("box_id") or symbol)
    return {"id": symbol, "kind": "doc", "label": label, "attr": attr, "in": [], "out": []}


def _provider_metadata_for_graph(metadata: Mapping[str, object]) -> Dict[str, object]:
    values = {
        "providers": _string_values(metadata.get("provider"), metadata.get("providers")),
        "models": _string_values(metadata.get("model"), metadata.get("models")),
        "job_ids": _string_values(metadata.get("job_id"), metadata.get("job_ids")),
    }
    return {key: _dedupe_strings(value) for key, value in values.items() if value}


def _function_concept_for_graph(
    function_name: str,
    metadata: Mapping[str, object],
    function_view: str,
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
) -> Dict[str, object]:
    if function_view != "concept":
        return {}
    for profile_id, rule in _function_normalization_rule_entries_for_metadata(metadata, function_rules_by_profile):
        if not rule.enabled:
            continue
        match = re.match(rule.match, function_name)
        if not match:
            continue
        values = match.groupdict()
        try:
            canonical = rule.canonical.format(**values)
        except KeyError:
            continue
        result: Dict[str, object] = {
            "rule_id": rule.id,
            "profile_id": profile_id,
            "function_name": canonical,
        }
        if values.get("ip_block"):
            result["ip_block"] = values["ip_block"]
        if values.get("ip_version"):
            result["ip_version"] = values["ip_version"]
        return result
    return {}


def _doc_page_for_graph(metadata: Mapping[str, object], anchor: str) -> int:
    try:
        page = int(metadata.get("page") or 0)
    except (TypeError, ValueError):
        page = 0
    if page:
        return page
    match = re.match(r"page-(\d+)$", anchor)
    return int(match.group(1)) if match else 0


def _function_normalization_rules_for_metadata(
    metadata: Mapping[str, object],
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
) -> tuple[GraphFunctionNormalizationRule, ...]:
    return tuple(
        rule for _profile_id, rule in _function_normalization_rule_entries_for_metadata(metadata, function_rules_by_profile)
    )


def _function_normalization_rule_entries_for_metadata(
    metadata: Mapping[str, object],
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
) -> tuple[tuple[str, GraphFunctionNormalizationRule], ...]:
    rules_by_profile = (
        _default_function_normalization_rules_by_profile()
        if function_rules_by_profile is None
        else function_rules_by_profile
    )
    resolver_profile_ids = _resolver_profile_ids_for_graph(metadata)
    if not resolver_profile_ids:
        resolver_profile_ids = _inferred_function_normalization_profile_ids_for_graph(metadata, rules_by_profile)
    if resolver_profile_ids:
        rules: List[tuple[str, GraphFunctionNormalizationRule]] = []
        for profile_id in resolver_profile_ids:
            rules.extend((profile_id, rule) for rule in rules_by_profile.get(profile_id, ()))
        return tuple(rules)
    return ()


def _inferred_function_normalization_profile_ids_for_graph(
    metadata: Mapping[str, object],
    rules_by_profile: Mapping[str, tuple[GraphFunctionNormalizationRule, ...]],
) -> List[str]:
    candidates: List[str] = []
    for key in ("corpus_id", "repo"):
        candidates.extend(_string_values(metadata.get(key)))
    source = metadata.get("source")
    if isinstance(source, list):
        for record in source:
            if isinstance(record, Mapping):
                for key in ("corpus_id", "repo"):
                    candidates.extend(_string_values(record.get(key)))
    profile_ids: List[str] = []
    for candidate in candidates:
        for profile_id in (candidate, _slug_for_graph_heading(candidate)):
            if profile_id in rules_by_profile:
                profile_ids.append(_canonical_default_resolver_profile_id_for_graph_alias(profile_id))
    return _dedupe_strings(profile_ids)


@lru_cache(maxsize=1)
def _default_resolver_profile_ids_by_graph_alias() -> Dict[str, str]:
    resolver_dir = _repo_root_for_storage_graph() / "configs" / "resolvers"
    if not resolver_dir.exists():
        return {}
    try:
        profiles = load_resolver_profiles(resolver_dir)
    except Exception:
        return {}
    aliases: Dict[str, str] = {}
    for profile in profiles.values():
        for alias in _dedupe_strings([profile.id, *profile.aliases]):
            aliases[alias] = profile.id
    return aliases


def _canonical_default_resolver_profile_id_for_graph_alias(profile_id: str) -> str:
    return _default_resolver_profile_ids_by_graph_alias().get(profile_id, profile_id)


def _register_normalization_for_metadata(
    metadata: Mapping[str, object],
    register_normalization_by_profile: Optional[Mapping[str, GraphRegisterNormalization]] = None,
) -> GraphRegisterNormalization:
    normalizations_by_profile = (
        _default_register_normalization_by_profile()
        if register_normalization_by_profile is None
        else register_normalization_by_profile
    )
    for profile_id in _resolver_profile_ids_for_graph(metadata):
        normalization = normalizations_by_profile.get(profile_id)
        if normalization is not None:
            return normalization
    return GraphRegisterNormalization()


def _register_node_id_for_graph(
    register_symbol: str,
    ip: str,
    ip_version: str,
    register_normalization: GraphRegisterNormalization,
) -> str:
    identity = register_normalization.identity or GraphRegisterNormalization().identity
    if not register_normalization.merge_across_ip_blocks and "{ip}" not in identity:
        identity = f"{identity}:{{ip}}"
    if not register_normalization.merge_across_ip_versions and "{ip_version}" not in identity:
        identity = f"{identity}:{{ip_version}}"
    values = {
        "symbol": register_symbol,
        "ip": ip,
        "ip_version": ip_version,
    }
    try:
        node_id = identity.format(**values)
    except (KeyError, ValueError):
        node_id = GraphRegisterNormalization().identity.format(**values)
    node_id = re.sub(r":+", ":", str(node_id).strip())
    if not node_id.startswith("register:"):
        node_id = f"register:{node_id}"
    return node_id


def _resolver_profile_ids_for_graph(metadata: Mapping[str, object]) -> List[str]:
    return _dedupe_strings(
        [
            *_string_values(metadata.get("resolver_profile_ids")),
            *_string_values(metadata.get("resolver_profiles")),
            *_string_values(metadata.get("resolver_profile")),
        ]
    )


@lru_cache(maxsize=1)
def _default_function_normalization_rules_by_profile() -> Dict[str, tuple[GraphFunctionNormalizationRule, ...]]:
    resolver_dir = _repo_root_for_storage_graph() / "configs" / "resolvers"
    if not resolver_dir.exists():
        return {}
    try:
        profiles = load_resolver_profiles(resolver_dir)
    except Exception:
        return {}
    rules_by_profile: Dict[str, tuple[GraphFunctionNormalizationRule, ...]] = {}
    for profile in profiles.values():
        function_normalization = profile.graph.function_normalization
        if function_normalization.enabled:
            rules = tuple(rule for rule in function_normalization.rules if rule.enabled)
        else:
            rules = ()
        for alias in _dedupe_strings([profile.id, *profile.aliases]):
            rules_by_profile[alias] = rules
    return rules_by_profile


@lru_cache(maxsize=1)
def _default_register_normalization_by_profile() -> Dict[str, GraphRegisterNormalization]:
    resolver_dir = _repo_root_for_storage_graph() / "configs" / "resolvers"
    if not resolver_dir.exists():
        return {}
    try:
        profiles = load_resolver_profiles(resolver_dir)
    except Exception:
        return {}
    normalization_by_profile: Dict[str, GraphRegisterNormalization] = {}
    for profile in profiles.values():
        for alias in _dedupe_strings([profile.id, *profile.aliases]):
            normalization_by_profile[alias] = profile.graph.register_normalization
    return normalization_by_profile


def _resolver_profile_from_graph_row(row: Mapping[str, object]) -> Optional[object]:
    profile_id = str(row.get("id") or "")
    config = row.get("config", {})
    if isinstance(config, Mapping) and config:
        try:
            return resolver_profile_from_config(config, fallback_id=profile_id)
        except Exception:
            return None
    config_path = _resolver_config_path_for_graph(str(row.get("path") or ""))
    if config_path.exists():
        try:
            return load_resolver_profile(config_path)
        except Exception:
            return None
    return None


def _resolver_profile_aliases_for_graph_row(row: Mapping[str, object], profile: Optional[object]) -> List[str]:
    aliases = [str(row.get("id") or "")]
    profile_id = str(getattr(profile, "id", "") or "")
    if profile_id:
        aliases.append(profile_id)
    aliases.extend(str(alias) for alias in getattr(profile, "aliases", []) or [])
    return _dedupe_strings(aliases)


def _resolver_config_path_for_graph(path: str) -> Path:
    config_path = Path(path)
    if config_path.is_absolute():
        return config_path
    return _repo_root_for_storage_graph() / config_path


def _repo_root_for_storage_graph() -> Path:
    return Path(__file__).resolve().parents[4]


def _function_raw_implementation(
    function_name: str,
    path: str,
    metadata: Mapping[str, object],
    source: List[Mapping[str, object]],
) -> Dict[str, object]:
    primary_source = source[0] if source else {}
    implementation = {
        "raw_function_name": function_name,
        "path": path,
        "corpus_id": str(primary_source.get("corpus_id") or metadata.get("corpus_id") or "unknown"),
        "repo": str(primary_source.get("repo") or metadata.get("repo") or "unknown"),
        "language": str(metadata.get("language") or _language_for_graph_path(path)),
    }
    for key in ("line_start", "line_end", "ip", "ip_version", "extractor", "resolver_profile"):
        value = metadata.get(key) or primary_source.get(key)
        if value not in ("", None, 0):
            implementation[key] = value
    return implementation


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
    attr["ip_versions"] = _dedupe_strings(
        [
            *_string_values(attr.get("ip_versions")),
            *_string_values(attr.get("ip_version")),
            *[
                str(item.get("ip_version") or "")
                for item in attr["source"]
                if isinstance(item, Mapping)
            ],
        ]
    )
    attr["resolver_wrappers"] = _dedupe_strings(_string_values(attr.get("resolver_wrappers")))
    attr["providers"] = _dedupe_strings(_string_values(attr.get("providers"), attr.get("provider")))
    attr["models"] = _dedupe_strings(_string_values(attr.get("models"), attr.get("model")))
    attr["job_ids"] = _dedupe_strings(_string_values(attr.get("job_ids"), attr.get("job_id")))
    attr["raw_function_names"] = _dedupe_strings(_string_values(attr.get("raw_function_names")))
    attr["raw_implementations"] = _dedupe_mapping_records(
        attr.get("raw_implementations") if isinstance(attr.get("raw_implementations"), list) else []
    )
    payload["attr"] = attr
    payload["in"] = _dedupe_strings(_string_values(payload.get("in")))
    payload["out"] = _dedupe_strings(_string_values(payload.get("out")))
    return payload


def _remember_compact_graph_node(node_metadata: Dict[str, Dict[str, object]], node: Mapping[str, object]) -> None:
    node_id = str(node.get("id") or "")
    if not node_id:
        return
    existing = node_metadata.setdefault(node_id, {})
    attr = node.get("attr") if isinstance(node.get("attr"), Mapping) else {}
    compact_attr = existing.setdefault("attr", {})
    if not isinstance(compact_attr, dict):
        compact_attr = {}
        existing["attr"] = compact_attr
    for key in (
        "doc_kind",
        "fields",
        "ip_versions",
        "providers",
        "models",
        "job_ids",
        "raw_function_names",
        "function_name",
        "ip_block",
        "normalization_rule",
        "merge_status",
    ):
        value = attr.get(key)
        if value not in (None, "", [], {}):
            if isinstance(value, list):
                compact_attr[key] = _dedupe_strings(
                    [*_string_values(compact_attr.get(key)), *_string_values(value)]
                )
            else:
                compact_attr.setdefault(key, value)
    raw_implementations = attr.get("raw_implementations")
    if isinstance(raw_implementations, list) and raw_implementations:
        existing_raw_implementations = (
            compact_attr.get("raw_implementations")
            if isinstance(compact_attr.get("raw_implementations"), list)
            else []
        )
        compact_attr["raw_implementations"] = _dedupe_mapping_records(
            [*existing_raw_implementations, *raw_implementations]
        )
    source_records = _source_records_for_graph(attr)[:1]
    if source_records:
        compact_attr.setdefault("source", source_records)
    label = str(node.get("label") or "")
    if label:
        existing.setdefault("label", label)
    kind = str(node.get("kind") or "")
    if kind:
        existing.setdefault("kind", kind)


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
    for list_key in (
        "fields",
        "resolver_wrappers",
        "ip_versions",
        "inputs",
        "outputs",
        "constraints",
        "raw_function_names",
        "resolver_profile_ids",
        "providers",
        "models",
        "job_ids",
    ):
        target_attr[list_key] = _dedupe_strings(
            [*_string_values(target_attr.get(list_key)), *_string_values(incoming_attr.get(list_key))]
        )
    target_attr["raw_implementations"] = _dedupe_mapping_records(
        [
            *(
                target_attr.get("raw_implementations")
                if isinstance(target_attr.get("raw_implementations"), list)
                else []
            ),
            *(
                incoming_attr.get("raw_implementations")
                if isinstance(incoming_attr.get("raw_implementations"), list)
                else []
            ),
        ]
    )
    incoming_ip_version = incoming_attr.get("ip_version")
    if incoming_ip_version not in ("", None, 0):
        target_attr["ip_versions"] = _dedupe_strings(
            [*_string_values(target_attr.get("ip_versions")), str(incoming_ip_version)]
        )
    for key, value in incoming_attr.items():
        if key in {
            "source",
            "fields",
            "resolver_wrappers",
            "ip_versions",
            "inputs",
            "outputs",
            "constraints",
            "raw_function_names",
            "raw_implementations",
            "resolver_profile_ids",
            "providers",
            "models",
            "job_ids",
        }:
            continue
        if value in ("", None, 0) and key != "register_neighbor_overlap":
            continue
        if key == "ip_version":
            target_attr.setdefault("ip_version", value)
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
        stats.setdefault("fields", set()).add(field_name)
    for provider in _string_values(attr.get("provider"), attr.get("providers")):
        stats.setdefault("providers", set()).add(provider)
    for model in _string_values(attr.get("model"), attr.get("models")):
        stats.setdefault("models", set()).add(model)
    for job_id in _string_values(attr.get("job_id"), attr.get("job_ids")):
        stats.setdefault("job_ids", set()).add(job_id)
    for profile_id in _resolver_profile_ids_for_graph(attr):
        stats.setdefault("resolver_profile_ids", set()).add(profile_id)
    for wrapper in _string_values(attr.get("resolver_wrappers")):
        stats.setdefault("resolver_wrappers", set()).add(wrapper)
    source_records = stats.get("source_records")
    if isinstance(source_records, list):
        source_records.extend(_source_records_for_graph(attr))
    raw_implementations = stats.get("raw_implementations")
    if isinstance(raw_implementations, list) and isinstance(attr.get("raw_implementations"), list):
        raw_implementations.extend(attr.get("raw_implementations") or [])
    for call_kind in _string_values(attr.get("call_kind")):
        stats.setdefault("call_kinds", set()).add(call_kind)
    for dispatch_scope in _string_values(attr.get("dispatch_scope")):
        stats.setdefault("dispatch_scopes", set()).add(dispatch_scope)
    for candidate_count in _string_values(attr.get("callback_candidate_count")):
        stats.setdefault("callback_candidate_counts", set()).add(candidate_count)
    if _bool_graph_value(attr.get("callback_ambiguous")):
        stats["callback_ambiguous"] = True


def _merge_callback_dispatch_stats(
    stats: Dict[str, object],
    src_metadata: Mapping[str, object],
    dst_metadata: Mapping[str, object],
) -> None:
    for metadata in (src_metadata, dst_metadata):
        for call_kind in _string_values(metadata.get("call_kind")):
            stats.setdefault("call_kinds", set()).add(call_kind)
        for dispatch_scope in _string_values(metadata.get("dispatch_scope")):
            stats.setdefault("dispatch_scopes", set()).add(dispatch_scope)
        for candidate_count in _string_values(metadata.get("callback_candidate_count")):
            stats.setdefault("callback_candidate_counts", set()).add(candidate_count)
        if _bool_graph_value(metadata.get("callback_ambiguous")):
            stats["callback_ambiguous"] = True


def _edge_attr_payload(stats: Mapping[str, object]) -> Dict[str, object]:
    payload = {
        "source": _dedupe_source_records(stats.get("source_records", []) if isinstance(stats.get("source_records"), list) else []),
        "fields": sorted(str(value) for value in stats.get("fields", set()) if value),
        "providers": sorted(str(value) for value in stats.get("providers", set()) if value),
        "models": sorted(str(value) for value in stats.get("models", set()) if value),
        "job_ids": sorted(str(value) for value in stats.get("job_ids", set()) if value),
        "resolver_profile_ids": sorted(str(value) for value in stats.get("resolver_profile_ids", set()) if value),
        "resolver_wrappers": sorted(str(value) for value in stats.get("resolver_wrappers", set()) if value),
    }
    raw_implementations = _dedupe_mapping_records(
        stats.get("raw_implementations", []) if isinstance(stats.get("raw_implementations"), list) else []
    )
    if raw_implementations:
        payload["implementations"] = raw_implementations
    original_relations = sorted(str(value) for value in stats.get("original_relations", set()) if value)
    if original_relations:
        payload["original_relation"] = original_relations[0] if len(original_relations) == 1 else original_relations
    dispatch = _dispatch_payload_value(stats.get("dispatch_scopes", set()))
    if dispatch:
        payload["dispatch"] = dispatch
    call_kinds = sorted(str(value) for value in stats.get("call_kinds", set()) if value)
    if call_kinds:
        payload["call_kind"] = call_kinds[0] if len(call_kinds) == 1 else call_kinds
    candidate_counts = sorted(
        int(value)
        for value in stats.get("callback_candidate_counts", set())
        if _int_graph_value(value)
    )
    if candidate_counts:
        payload["callback_candidate_count"] = max(candidate_counts)
    if stats.get("callback_ambiguous"):
        payload["callback_ambiguous"] = True
    return payload


def _apply_callback_dispatch_edge_attr(
    edge_attr: Dict[str, object],
    src_metadata: Mapping[str, object],
    dst_metadata: Mapping[str, object],
) -> None:
    dispatch = _dispatch_payload_value(
        [
            *_string_values(src_metadata.get("dispatch_scope")),
            *_string_values(dst_metadata.get("dispatch_scope")),
        ]
    )
    if dispatch:
        edge_attr["dispatch"] = dispatch
    call_kinds = _dedupe_strings(
        [
            *_string_values(src_metadata.get("call_kind")),
            *_string_values(dst_metadata.get("call_kind")),
        ]
    )
    if call_kinds:
        edge_attr["call_kind"] = call_kinds[0] if len(call_kinds) == 1 else call_kinds
    candidate_counts = [
        _int_graph_value(value)
        for value in [
            *_string_values(src_metadata.get("callback_candidate_count")),
            *_string_values(dst_metadata.get("callback_candidate_count")),
        ]
        if _int_graph_value(value)
    ]
    if candidate_counts:
        edge_attr["callback_candidate_count"] = max(candidate_counts)
    if _bool_graph_value(src_metadata.get("callback_ambiguous")) or _bool_graph_value(dst_metadata.get("callback_ambiguous")):
        edge_attr["callback_ambiguous"] = True


def _dispatch_payload_value(values: Iterable[object]) -> str:
    scopes = {str(value) for value in values if value}
    if "ambiguous" in scopes:
        return "ambiguous"
    if "generic_slot" in scopes:
        return "generic_slot"
    if "matched_slot" in scopes:
        return "matched_slot"
    return ""


def _bool_graph_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _original_relations_for_graph_edge(
    relation: str,
    original_relation: str,
    *metadata_items: Mapping[str, object],
) -> List[str]:
    originals: List[str] = []
    if original_relation and original_relation != relation:
        originals.append(original_relation)
    for metadata in metadata_items:
        originals.extend(_string_values(metadata.get("original_relation"), metadata.get("original_relations")))
    return [value for value in _dedupe_strings(originals) if value and value != relation]


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


def _mark_function_concept_divergence(
    node_metadata: Dict[str, Dict[str, object]],
    edges: Iterable[Mapping[str, object]],
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
) -> None:
    register_neighbors: Dict[str, set[str]] = {}
    implementation_neighbors: Dict[str, Dict[str, set[str]]] = {}
    for edge in edges:
        src = str(edge.get("src") or "")
        dst = str(edge.get("dst") or "")
        relation = str(edge.get("relation") or "")
        if relation not in {"reads", "writes", "sets_field", "maps_base"}:
            continue
        concept_id = ""
        register_id = ""
        if ":concept:" in src and dst.startswith("register:"):
            concept_id = src
            register_id = dst
        elif ":concept:" in dst and src.startswith("register:"):
            concept_id = dst
            register_id = src
        if not concept_id or not register_id:
            continue
        register_neighbors.setdefault(concept_id, set()).add(register_id)
        edge_attr = edge.get("attr") if isinstance(edge.get("attr"), Mapping) else {}
        implementations = edge_attr.get("implementations")
        if isinstance(implementations, list):
            for implementation in implementations:
                if not isinstance(implementation, Mapping):
                    continue
                implementation_key = _implementation_overlap_key(implementation)
                if implementation_key:
                    implementation_neighbors.setdefault(concept_id, {}).setdefault(implementation_key, set()).add(
                        register_id
                    )
    for node_id, neighbors in register_neighbors.items():
        metadata = node_metadata.get(node_id)
        if not metadata or len(neighbors) < 2:
            continue
        attr = metadata.setdefault("attr", {})
        if isinstance(attr, dict):
            raw_implementations = attr.get("raw_implementations")
            if isinstance(raw_implementations, list) and len(raw_implementations) > 1:
                overlap = _minimum_register_neighbor_overlap(implementation_neighbors.get(node_id, {}))
                if overlap is not None:
                    attr["register_neighbor_overlap"] = round(overlap, 4)
                normalization_profile_id = str(attr.get("normalization_profile_id") or "")
                policy_profile_ids = [normalization_profile_id] if normalization_profile_id else _resolver_profile_ids_for_graph(attr)
                policy = _function_merge_policy_for_rule(
                    str(attr.get("normalization_rule") or ""),
                    resolver_profile_ids=policy_profile_ids,
                    function_rules_by_profile=function_rules_by_profile,
                )
                if overlap is not None and overlap < policy.split_register_overlap_below:
                    attr["merge_status"] = "split_recommended"
                elif overlap is not None and overlap < policy.warn_register_overlap_below:
                    attr["merge_status"] = "divergent"
                elif overlap is not None:
                    attr["merge_status"] = "merged"
                else:
                    attr["merge_status"] = "divergent"


def _implementation_overlap_key(implementation: Mapping[str, object]) -> str:
    raw_name = str(implementation.get("raw_function_name") or "")
    path = str(implementation.get("path") or "")
    return f"{path}:{raw_name}" if raw_name else path


def _minimum_register_neighbor_overlap(implementation_neighbors: Mapping[str, set[str]]) -> Optional[float]:
    neighbor_sets = [set(neighbors) for neighbors in implementation_neighbors.values() if neighbors]
    if len(neighbor_sets) < 2:
        return None
    minimum = 1.0
    for left, right in combinations(neighbor_sets, 2):
        union = left | right
        if not union:
            continue
        minimum = min(minimum, len(left & right) / len(union))
    return minimum


def _function_merge_policy_for_rule(
    rule_id: str,
    resolver_profile_ids: Optional[Iterable[str]] = None,
    function_rules_by_profile: Optional[Mapping[str, tuple[GraphFunctionNormalizationRule, ...]]] = None,
) -> GraphMergePolicy:
    rules_by_profile = (
        _default_function_normalization_rules_by_profile()
        if function_rules_by_profile is None
        else function_rules_by_profile
    )
    selected_profile_ids = _dedupe_strings(str(profile_id) for profile_id in (resolver_profile_ids or []))
    if selected_profile_ids:
        profile_rule_sets = [rules_by_profile.get(profile_id, ()) for profile_id in selected_profile_ids]
    else:
        profile_rule_sets = list(rules_by_profile.values())
    for profile_rules in profile_rule_sets:
        for rule in profile_rules:
            if rule.id == rule_id:
                return rule.merge_policy
    return GraphMergePolicy()


def _source_records_for_graph(metadata: Mapping[str, object]) -> List[Dict[str, object]]:
    raw_source = metadata.get("source")
    if isinstance(raw_source, list):
        return _dedupe_source_records(raw_source)
    record = {
        "corpus_id": str(metadata.get("corpus_id") or "unknown"),
        "repo": str(metadata.get("repo") or "unknown"),
        "path": str(metadata.get("path") or ""),
    }
    for key in ("line_start", "line_end", "page", "commit", "snippet_id", "resolver_profile"):
        value = metadata.get(key)
        if value not in ("", None, 0):
            record[key] = value
    for key in ("ip", "ip_version"):
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
        for key in ("line_start", "line_end", "page", "commit", "snippet_id", "ip", "ip_version", "resolver_profile"):
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


def _dedupe_mapping_records(records: Iterable[object]) -> List[Dict[str, object]]:
    result: List[Dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            continue
        record = {str(key): value for key, value in raw_record.items() if value not in ("", None, 0)}
        key = tuple(sorted((key, json.dumps(value, sort_keys=True, default=str)) for key, value in record.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


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
    offset = snippet.find(symbol)
    while offset >= 0:
        before = snippet[offset - 1] if offset > 0 else ""
        if not before or not _is_c_identifier_char(before):
            cursor = offset + len(symbol)
            while cursor < len(snippet) and snippet[cursor].isspace():
                cursor += 1
            if cursor < len(snippet) and snippet[cursor] == "(":
                return True
        offset = snippet.find(symbol, offset + 1)
    return False


def _is_c_identifier_char(value: str) -> bool:
    return value == "_" or value.isalnum()


def _merge_graph_metadata(base: Mapping[str, object], override: Optional[Mapping[str, object]]) -> Dict[str, object]:
    merged = dict(base)
    for key, value in dict(override or {}).items():
        if value not in ("", None, 0):
            merged[key] = value
    return merged


def _tokens_look_like_exact_symbols(tokens: Iterable[str]) -> bool:
    token_list = [str(token).strip() for token in tokens if str(token).strip()]
    if not token_list:
        return False
    return all("_" in token or re.search(r"\d", token) for token in token_list)


def _symbol_aliases_for_query_tokens(tokens: Iterable[str]) -> List[str]:
    aliases: List[str] = []
    for token in tokens:
        text = str(token).strip()
        if not text:
            continue
        variants = [text]
        upper = text.upper()
        lower = text.lower()
        for candidate in (upper, lower):
            if candidate not in variants:
                variants.append(candidate)
        if _tokens_look_like_exact_symbols([text]):
            canonical = _register_symbol_for_graph(upper)
            for prefix in ("", "reg", "mm", "smn"):
                candidate = f"{prefix}{canonical}" if prefix else canonical
                if candidate not in variants:
                    variants.append(candidate)
        aliases.extend(variants)
    return _dedupe_strings(aliases)


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
    if normalized in {"register"}:
        return "register"
    if normalized in {"macro", "context"}:
        return "macro"
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
    return normalize_product_relation(relation) or ""


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
    if re.match(r"^CP_HQD_", symbol):
        return "register"
    if _has_register_prefix_alias(symbol) or re.search(
        r"CNTL|CONTROL|STATUS|RESET|BASE|SIZE|VMID|DOORBELL|QUEUE|REGISTER",
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
    return "relates_to"


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


def _section_node_for_graph_mapping(row: Mapping[str, object]) -> tuple[str, str, Dict[str, object]]:
    source_type = str(row.get("source_type") or row.get("source") or "")
    if source_type not in {"doc", "pdf"}:
        return "", "", {}
    path = str(row.get("path") or "").strip()
    if not path:
        return "", "", {}
    chunk_text = str(row.get("chunk_text") or row.get("snippet") or "")
    heading = _first_markdown_heading(chunk_text)
    page = _int_graph_value(row.get("page"))
    line_start = _int_graph_value(row.get("line_start"))
    if heading:
        section_id = f"{path}#{_slug_for_graph_heading(heading)}"
    elif source_type == "pdf" and page:
        section_id = f"{path}#page-{page}"
    elif line_start:
        section_id = f"{path}#lines-{line_start}"
    else:
        section_id = f"{path}#section"
    section_kind = "doc_section" if source_type == "doc" else "pdf_section"
    anchor = _anchor_for_graph_symbol(section_id)
    metadata: Dict[str, object] = {
        "source_type": source_type,
        "path": path,
        "anchor": anchor,
        "label": _section_label_for_graph(path, source_type, anchor, heading, page, line_start),
        "corpus_id": str(row.get("corpus_id") or ""),
        "repo": str(row.get("repo") or ""),
    }
    if heading:
        metadata["heading"] = heading
    if page:
        metadata["page"] = page
    if line_start:
        metadata["line_start"] = line_start
    line_end = _int_graph_value(row.get("line_end"))
    if line_end:
        metadata["line_end"] = line_end
    return section_id, section_kind, {key: value for key, value in metadata.items() if value not in ("", None, 0)}


def _metadata_for_graph_mapping(row: Mapping[str, object], endpoint: str) -> Dict[str, object]:
    metadata: Dict[str, object] = {
        "path": str(row.get("path") or ""),
        "line_start": row.get("line_start"),
        "line_end": row.get("line_end"),
        "page": row.get("page"),
        "corpus_id": str(row.get("corpus_id") or ""),
        "repo": str(row.get("repo") or ""),
        "source_type": str(row.get("source_type") or row.get("source") or ""),
        "symbol": endpoint,
    }
    if _looks_like_function_symbol(endpoint):
        metadata["function_name"] = endpoint
    return {key: value for key, value in metadata.items() if value not in ("", None, 0)}


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


def _int_graph_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
        "resolver_profile",
        "resolver_profile_ids",
        "resolver_wrappers",
        "wrapper",
        "job_id",
        "original_relation",
        "original_relations",
        "call_kind",
        "dispatch_scope",
        "callback_ambiguous",
        "callback_candidate_count",
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
        "resolver_profile",
        "resolver_profile_ids",
        "resolver_wrappers",
        "wrapper",
        "job_id",
        "original_relation",
        "original_relations",
        "call_kind",
        "dispatch_scope",
        "callback_ambiguous",
        "callback_candidate_count",
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
    protected_budget = min(len(protected), limit)
    bridge_budget = max(0, limit - protected_budget)
    shared_register_bridges = _shared_register_bridge_edges(edges, bridge_budget)
    remaining_budget = max(0, limit - protected_budget - len(shared_register_bridges))
    call_backbone_budget = max(1, remaining_budget - max(0, remaining_budget // 5)) if remaining_budget else 0
    call_backbone = _largest_call_backbone_edges(edges, call_backbone_budget)
    operation_backbone = _operation_edges_adjacent_to_backbone(edges, call_backbone, remaining_budget - len(call_backbone))
    selected: List[Dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in [*protected, *shared_register_bridges, *call_backbone, *operation_backbone, *edges]:
        key = (str(edge["src"]), str(edge["dst"]), str(edge["relation"]))
        if key in seen:
            continue
        seen.add(key)
        selected.append(edge)
        if len(selected) >= limit:
            break
    return selected


def _shared_register_bridge_edges(edges: List[Dict[str, object]], budget: int) -> List[Dict[str, object]]:
    if budget <= 1:
        return []
    candidate_budget = min(max(2, int(budget) // 10), int(budget))
    operation_relations = {"reads", "writes", "sets_field", "maps_base"}
    by_register: Dict[str, Dict[str, List[Dict[str, object]]]] = {}
    for edge in edges:
        if str(edge.get("relation") or "") not in operation_relations or _is_protected_global_edge(edge):
            continue
        src = str(edge.get("src") or "")
        dst = str(edge.get("dst") or "")
        register_id = src if _is_register_graph_node_id(src) else dst if _is_register_graph_node_id(dst) else ""
        function_id = dst if register_id == src else src
        function_scope = _function_scope_for_graph_node_id(function_id)
        if not register_id or not function_scope:
            continue
        by_register.setdefault(register_id, {}).setdefault(function_scope, []).append(edge)

    groups = [
        (register_id, scoped_edges)
        for register_id, scoped_edges in by_register.items()
        if len(scoped_edges) > 1
    ]
    groups.sort(
        key=lambda item: (
            -len(item[1]),
            -sum(int(edge.get("count") or 0) for edges_for_scope in item[1].values() for edge in edges_for_scope),
            item[0],
        )
    )

    selected: List[Dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for _register_id, scoped_edges in groups:
        for _scope, scope_edges in sorted(scoped_edges.items()):
            best = sorted(
                scope_edges,
                key=lambda edge: (
                    -float(edge.get("weight") or edge.get("confidence") or 0),
                    -int(edge.get("count") or 0),
                    str(edge.get("src") or ""),
                    str(edge.get("dst") or ""),
                    str(edge.get("relation") or ""),
                ),
            )[0]
            key = (str(best.get("src") or ""), str(best.get("dst") or ""), str(best.get("relation") or ""))
            if key in seen:
                continue
            selected.append(best)
            seen.add(key)
            if len(selected) >= candidate_budget:
                return selected
    return selected


def _largest_call_backbone_edges(edges: List[Dict[str, object]], budget: int) -> List[Dict[str, object]]:
    if budget <= 0:
        return []
    call_edges = [
        edge
        for edge in edges
        if str(edge.get("relation") or "") == "calls" and not _is_protected_global_edge(edge)
    ]
    if not call_edges:
        return []

    adjacency: Dict[str, set[str]] = {}
    for edge in call_edges:
        src = str(edge.get("src") or "")
        dst = str(edge.get("dst") or "")
        if not src or not dst:
            continue
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)

    seen_nodes: set[str] = set()
    components: List[set[str]] = []
    for node in adjacency:
        if node in seen_nodes:
            continue
        stack = [node]
        seen_nodes.add(node)
        component: set[str] = set()
        while stack:
            current = stack.pop()
            component.add(current)
            for neighbor in adjacency.get(current, ()):
                if neighbor not in seen_nodes:
                    seen_nodes.add(neighbor)
                    stack.append(neighbor)
        components.append(component)

    component_rank = {node: index for index, component in enumerate(
        sorted(components, key=lambda item: (-len(item), sorted(item)[0] if item else ""))
    ) for node in component}
    ranked_edges = sorted(
        call_edges,
        key=lambda edge: (
            component_rank.get(str(edge.get("src") or ""), len(components)),
            _call_backbone_priority(edge),
            str(edge.get("src") or ""),
            str(edge.get("dst") or ""),
        ),
    )

    parent: Dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> bool:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return False
        parent[right_root] = left_root
        return True

    selected: List[Dict[str, object]] = []
    selected_keys: set[tuple[str, str, str]] = set()
    for edge in ranked_edges:
        if len(selected) >= budget:
            break
        src = str(edge.get("src") or "")
        dst = str(edge.get("dst") or "")
        key = (src, dst, str(edge.get("relation") or ""))
        if not src or not dst or key in selected_keys:
            continue
        if union(src, dst):
            selected.append(edge)
            selected_keys.add(key)

    for edge in ranked_edges:
        if len(selected) >= budget:
            break
        key = (str(edge.get("src") or ""), str(edge.get("dst") or ""), str(edge.get("relation") or ""))
        if key in selected_keys:
            continue
        selected.append(edge)
        selected_keys.add(key)
    return selected


def _operation_edges_adjacent_to_backbone(
    edges: List[Dict[str, object]],
    backbone_edges: List[Dict[str, object]],
    budget: int,
) -> List[Dict[str, object]]:
    if budget <= 0 or not backbone_edges:
        return []
    backbone_nodes = {
        str(value)
        for edge in backbone_edges
        for value in (edge.get("src"), edge.get("dst"))
        if str(value or "")
    }
    operation_edges = [
        edge
        for edge in edges
        if str(edge.get("relation") or "") in {"reads", "writes", "sets_field", "maps_base"}
        and (
            str(edge.get("src") or "") in backbone_nodes
            or str(edge.get("dst") or "") in backbone_nodes
        )
        and not _is_protected_global_edge(edge)
    ]
    return sorted(
        operation_edges,
        key=lambda edge: (
            _graph_relation_priority(str(edge.get("relation") or "")),
            -float(edge.get("weight") or edge.get("confidence") or 0),
            str(edge.get("src") or ""),
            str(edge.get("dst") or ""),
        ),
    )[: max(0, int(budget))]


def _call_backbone_priority(edge: Mapping[str, object]) -> tuple[int, float, int]:
    sources = {str(source) for source in edge.get("sources", []) if source}
    source_priority = 0 if "clang_callback" in sources else 1
    return (source_priority, -float(edge.get("weight") or 0), -int(edge.get("count") or 0))


def _is_register_graph_node_id(node_id: str) -> bool:
    return node_id.startswith("register:")


def _function_scope_for_graph_node_id(node_id: str) -> str:
    if not node_id.startswith("function:"):
        return ""
    parts = node_id.split(":", 3)
    return parts[1] if len(parts) > 1 else ""


def _normalize_job_status(status: str) -> str:
    return normalize_job_status(status)


def normalize_job_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"queued", "indexing", "succeeded", "failed", "superseded"}:
        return normalized
    if normalized in {"running", "started", "in_progress"}:
        return "indexing"
    if normalized in {"error", "errored"}:
        return "failed"
    return "succeeded"


def _semantic_graph_job_matches_provider(row: sqlite3.Row, expected_provider: str, expected_model: str) -> bool:
    if not expected_provider and not expected_model:
        return True
    try:
        metadata = json.loads(str(row["metadata_json"] or "{}"))
    except json.JSONDecodeError:
        metadata = {}
    provider_settings = metadata.get("provider_settings") if isinstance(metadata, Mapping) else None
    edge_settings = provider_settings.get("edge") if isinstance(provider_settings, Mapping) else None
    if not isinstance(edge_settings, Mapping):
        return False
    provider = str(edge_settings.get("provider") or "ollama").strip()
    model = str(edge_settings.get("model") or edge_settings.get("preferred") or "").strip()
    if expected_provider and provider != expected_provider:
        return False
    if expected_model and model != expected_model:
        return False
    return True


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
