import sqlite3
import os
import json
import time
from typing import List, Optional, Dict, Any

from memory.types import (
    MemoryChunk,
    MemorySearchResult,
    MemorySource,
    HybridSearchConfig,
    TemporalDecayConfig,
    MMRConfig,
    MemoryProviderStatus,
)
from memory.files import (
    list_memory_files,
    chunk_markdown,
    read_memory_file,
    get_relative_path,
)
from memory.embedding import EmbeddingProvider, create_embedding_provider, compute_text_hash
from memory.postprocess import (
    merge_hybrid_results,
    apply_temporal_decay,
    apply_mmr,
    bm25_rank_to_score,
)


_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'memory',
    hash TEXT NOT NULL,
    mtime INTEGER NOT NULL,
    size INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'memory',
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    hash TEXT NOT NULL,
    model TEXT NOT NULL,
    text TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding_cache (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding TEXT NOT NULL,
    dims INTEGER,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (provider, model, content_hash)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, id UNINDEXED, path UNINDEXED, source UNINDEXED,
    model UNINDEXED, start_line UNINDEXED, end_line UNINDEXED
);
"""


def _row_get(row, key: str, default: str = "") -> str:
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError):
        return default


class MemoryIndexManager:
    def __init__(
        self,
        workspace_dir: str,
        agent_id: str = "default",
        db_path: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        hybrid_config: Optional[HybridSearchConfig] = None,
        temporal_decay_config: Optional[TemporalDecayConfig] = None,
        mmr_config: Optional[MMRConfig] = None,
    ):
        self.workspace_dir = workspace_dir
        self.agent_id = agent_id
        self._hybrid_config = hybrid_config or HybridSearchConfig()
        self._temporal_decay_config = temporal_decay_config or TemporalDecayConfig()
        self._mmr_config = mmr_config or MMRConfig()

        if db_path is None:
            db_dir = os.path.join(workspace_dir, ".miniclaw", "memory")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, f"{agent_id}.db")
        self._db_path = db_path

        self._provider = embedding_provider
        self._db: Optional[sqlite3.Connection] = None
        self._dirty = False
        self._last_sync_time = 0.0

    def _get_db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(self._db_path)
            self._db.row_factory = sqlite3.Row
            self._db.executescript(_MEMORY_SCHEMA)
            self._db.execute("PRAGMA journal_mode=WAL")
        return self._db

    def _close_db(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    async def ensure_provider(self):
        if self._provider is None:
            self._provider = create_embedding_provider(provider="auto")

    async def sync(self, force: bool = False):
        db = self._get_db()
        memory_files = list_memory_files(self.workspace_dir)
        current_files: Dict[str, Dict[str, Any]] = {}
        for fpath in memory_files:
            try:
                stat = os.stat(fpath)
                rel_path = get_relative_path(fpath, self.workspace_dir)
                current_files[rel_path] = {
                    "abs_path": fpath,
                    "mtime": int(stat.st_mtime),
                    "size": stat.st_size,
                }
            except OSError:
                continue

        existing_rows = db.execute("SELECT path, hash, mtime, size FROM files").fetchall()
        existing_map = {row["path"]: dict(row) for row in existing_rows}

        to_add = []
        to_update = []
        to_delete = []

        for rel_path, info in current_files.items():
            if rel_path not in existing_map:
                to_add.append(rel_path)
            else:
                existing = existing_map[rel_path]
                if existing["mtime"] != info["mtime"] or existing["size"] != info["size"]:
                    to_update.append(rel_path)

        for rel_path in existing_map:
            if rel_path not in current_files:
                to_delete.append(rel_path)

        if not to_add and not to_update and not to_delete and not force:
            return

        for rel_path in to_delete:
            self._delete_file_chunks(db, rel_path)
            db.execute("DELETE FROM files WHERE path = ?", (rel_path,))

        changed_paths = to_add + to_update
        for rel_path in changed_paths:
            info = current_files.get(rel_path)
            if not info:
                continue
            content = read_memory_file(info["abs_path"])
            if not content:
                continue
            content_hash = compute_text_hash(content)
            self._delete_file_chunks(db, rel_path)
            chunks = chunk_markdown(content)
            chunk_records = []
            for start_line, end_line, text in chunks:
                chunk_id = compute_text_hash(f"{rel_path}:{start_line}:{end_line}:{text}")
                chunk_records.append((chunk_id, rel_path, start_line, end_line, text, content_hash))

            if self._provider:
                texts = [r[4] for r in chunk_records]
                try:
                    embeddings = await self._provider.embed_batch(texts)
                    for i, (chunk_id, path, start, end, text, chash) in enumerate(chunk_records):
                        if i < len(embeddings):
                            emb_json = json.dumps(embeddings[i])
                            self._upsert_chunk_with_embedding(
                                db, chunk_id, path, start, end, text,
                                self._provider.model, emb_json,
                            )
                except Exception:
                    for chunk_id, path, start, end, text, chash in chunk_records:
                        self._upsert_chunk(db, chunk_id, path, start, end, text, "")
            else:
                for chunk_id, path, start, end, text, chash in chunk_records:
                    self._upsert_chunk(db, chunk_id, path, start, end, text, "")

            db.execute(
                "INSERT OR REPLACE INTO files (path, source, hash, mtime, size) VALUES (?, ?, ?, ?, ?)",
                (rel_path, "memory", content_hash, info["mtime"], info["size"]),
            )

        db.commit()
        self._last_sync_time = time.time()
        self._dirty = False

    def _delete_file_chunks(self, db: sqlite3.Connection, rel_path: str):
        chunk_ids = db.execute("SELECT id FROM chunks WHERE path = ?", (rel_path,)).fetchall()
        for row in chunk_ids:
            db.execute("DELETE FROM chunks_fts WHERE id = ?", (row["id"],))
        db.execute("DELETE FROM chunks WHERE path = ?", (rel_path,))

    def _upsert_chunk(
        self,
        db: sqlite3.Connection,
        chunk_id: str,
        path: str,
        start_line: int,
        end_line: int,
        text: str,
        model: str,
    ):
        now = int(time.time())
        db.execute(
            "INSERT OR REPLACE INTO chunks (id, path, source, start_line, end_line, hash, model, text, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, path, "memory", start_line, end_line, compute_text_hash(text), model, text, now),
        )
        db.execute(
            "INSERT OR REPLACE INTO chunks_fts (id, path, source, model, start_line, end_line, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, path, "memory", model, start_line, end_line, text),
        )

    def _upsert_chunk_with_embedding(
        self,
        db: sqlite3.Connection,
        chunk_id: str,
        path: str,
        start_line: int,
        end_line: int,
        text: str,
        model: str,
        embedding_json: str,
    ):
        self._upsert_chunk(db, chunk_id, path, start_line, end_line, text, model)
        now = int(time.time())
        db.execute(
            "INSERT OR REPLACE INTO embedding_cache (provider, model, content_hash, embedding, dims, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("local", model, chunk_id, embedding_json, len(json.loads(embedding_json)) if embedding_json else 0, now),
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        source: Optional[MemorySource] = None,
    ) -> List[MemorySearchResult]:
        if not query.strip():
            return []
        db = self._get_db()
        total = db.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
        if total == 0:
            await self.sync(force=True)
            total = db.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
            if total == 0:
                return []

        candidate_count = max_results * self._hybrid_config.candidate_multiplier
        source_filter = ""
        source_params: list = []
        if source:
            source_filter = "AND source = ?"
            source_params = [source.value]

        text_results = self._search_keyword(db, query, candidate_count, source_filter, source_params)
        vector_results: List[MemorySearchResult] = []

        if self._provider and self._hybrid_config.enabled:
            try:
                query_embedding = await self._provider.embed_query(query)
                vector_results = self._search_vector(db, query_embedding, candidate_count, source_filter, source_params)
            except Exception:
                vector_results = []

        if vector_results and text_results:
            results = merge_hybrid_results(
                vector_results,
                text_results,
                self._hybrid_config.vector_weight,
                self._hybrid_config.text_weight,
            )
        elif vector_results:
            results = vector_results
        elif text_results:
            results = text_results
        else:
            return []

        results = apply_temporal_decay(results, self._temporal_decay_config, self.workspace_dir)
        results = apply_mmr(results, self._mmr_config, max_results)
        return results[:max_results]

    def _search_keyword(
        self,
        db: sqlite3.Connection,
        query: str,
        limit: int,
        source_filter: str,
        source_params: list,
    ) -> List[MemorySearchResult]:
        try:
            fts_query = " OR ".join(query.split())
            rows = db.execute(
                f"SELECT id, path, source, start_line, end_line, text, model, bm25(chunks_fts) as rank "
                f"FROM chunks_fts WHERE chunks_fts MATCH ? {source_filter} ORDER BY rank ASC LIMIT ?",
                (fts_query, *source_params, limit),
            ).fetchall()
        except Exception:
            return []

        results = []
        for row in rows:
            score = bm25_rank_to_score(row["rank"])
            chunk = MemoryChunk(
                id=row["id"],
                path=row["path"],
                source=MemorySource(_row_get(row, "source", "memory")),
                start_line=row["start_line"],
                end_line=row["end_line"],
                text=row["text"],
                model=_row_get(row, "model", ""),
            )
            results.append(MemorySearchResult(chunk=chunk, score=score, text_score=score))
        return results

    def _search_vector(
        self,
        db: sqlite3.Connection,
        query_embedding: List[float],
        limit: int,
        source_filter: str,
        source_params: list,
    ) -> List[MemorySearchResult]:
        try:
            import numpy as np
        except ImportError:
            return []

        rows = db.execute(
            f"SELECT c.id, c.path, c.source, c.start_line, c.end_line, c.text, c.model "
            f"FROM chunks c WHERE 1=1 {source_filter}",
            source_params,
        ).fetchall()

        if not rows:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_vec = query_vec / query_norm

        scored = []
        for row in rows:
            chunk_id = row["id"]
            model_name = self._provider.model if self._provider else ""
            cache_row = db.execute(
                "SELECT embedding FROM embedding_cache WHERE provider = ? AND model = ? AND content_hash = ?",
                ("local", model_name, chunk_id),
            ).fetchone()

            if not cache_row:
                continue

            try:
                emb = json.loads(cache_row["embedding"])
            except (json.JSONDecodeError, TypeError):
                continue

            doc_vec = np.array(emb, dtype=np.float32)
            doc_norm = np.linalg.norm(doc_vec)
            if doc_norm == 0:
                continue
            doc_vec = doc_vec / doc_norm
            similarity = float(np.dot(query_vec, doc_vec))
            scored.append((similarity, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for similarity, row in scored[:limit]:
            chunk = MemoryChunk(
                id=row["id"],
                path=row["path"],
                source=MemorySource(_row_get(row, "source", "memory")),
                start_line=row["start_line"],
                end_line=row["end_line"],
                text=row["text"],
                model=_row_get(row, "model", ""),
            )
            score = max(0.0, (similarity + 1.0) / 2.0)
            results.append(MemorySearchResult(chunk=chunk, score=score, vector_score=score))
        return results

    def status(self) -> MemoryProviderStatus:
        db = self._get_db()
        total_chunks = db.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
        total_files = db.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
        fts_available = True
        try:
            db.execute("SELECT COUNT(*) FROM chunks_fts LIMIT 1")
        except Exception:
            fts_available = False

        return MemoryProviderStatus(
            available=True,
            vector_enabled=self._provider is not None,
            fts_enabled=fts_available,
            embedding_model=self._provider.model if self._provider else "",
            total_chunks=total_chunks,
            total_files=total_files,
            db_path=self._db_path,
        )

    def close(self):
        self._close_db()
        if self._provider:
            try:
                import asyncio
                asyncio.get_event_loop().run_until_complete(self._provider.close())
            except Exception:
                pass


_managers: Dict[str, MemoryIndexManager] = {}


def get_memory_manager(
    workspace_dir: str,
    agent_id: str = "default",
    **kwargs,
) -> MemoryIndexManager:
    cache_key = f"{workspace_dir}:{agent_id}"
    if cache_key not in _managers:
        _managers[cache_key] = MemoryIndexManager(
            workspace_dir=workspace_dir,
            agent_id=agent_id,
            **kwargs,
        )
    return _managers[cache_key]
