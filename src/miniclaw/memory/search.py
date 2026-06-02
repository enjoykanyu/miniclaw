import sqlite3
from typing import List, Optional

from miniclaw.memory.types import MemoryChunk, MemorySearchResult, MemorySource
from miniclaw.memory.postprocess import bm25_rank_to_score


def _row_get(row, key: str, default: str = "") -> str:
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError):
        return default


def search_fts(
    db: sqlite3.Connection,
    query: str,
    limit: int = 50,
    source: Optional[MemorySource] = None,
) -> List[MemorySearchResult]:
    source_filter = ""
    params: list = []
    if source:
        source_filter = "AND source = ?"
        params = [source.value]

    try:
        fts_query = " OR ".join(query.split())
        rows = db.execute(
            f"SELECT id, path, source, start_line, end_line, text, model, bm25(chunks_fts) as rank "
            f"FROM chunks_fts WHERE chunks_fts MATCH ? {source_filter} ORDER BY rank ASC LIMIT ?",
            (fts_query, *params, limit),
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


def search_vector(
    db: sqlite3.Connection,
    query_embedding: List[float],
    model: str,
    limit: int = 50,
    source: Optional[MemorySource] = None,
) -> List[MemorySearchResult]:
    try:
        import numpy as np
    except ImportError:
        return []

    source_filter = ""
    params: list = []
    if source:
        source_filter = "AND c.source = ?"
        params = [source.value]

    rows = db.execute(
        f"SELECT c.id, c.path, c.source, c.start_line, c.end_line, c.text, c.model "
        f"FROM chunks c WHERE 1=1 {source_filter}",
        params,
    ).fetchall()

    if not rows:
        return []

    query_vec = np.array(query_embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []
    query_vec = query_vec / query_norm

    import json
    scored = []
    for row in rows:
        cache_row = db.execute(
            "SELECT embedding FROM embedding_cache WHERE provider = ? AND model = ? AND content_hash = ?",
            ("local", model, row["id"]),
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
