import math
from datetime import datetime
from typing import List, Set, Dict, Tuple

from memory.types import MemorySearchResult, MemoryChunk, MMRConfig, TemporalDecayConfig
from memory.files import parse_date_from_memory_path, is_evergreen_path, get_relative_path


def apply_temporal_decay(
    results: List[MemorySearchResult],
    config: TemporalDecayConfig,
    workspace_dir: str = "",
) -> List[MemorySearchResult]:
    if not config.enabled:
        return results
    half_life = config.half_life_days
    if half_life <= 0:
        return results
    decay_lambda = math.log(2) / half_life
    now = datetime.now()
    for r in results:
        rel_path = get_relative_path(r.chunk.path, workspace_dir) if workspace_dir else r.chunk.path
        if is_evergreen_path(rel_path):
            continue
        file_date = parse_date_from_memory_path(rel_path)
        if file_date is None:
            continue
        age_days = (now - file_date).total_seconds() / 86400
        if age_days > 0:
            decay_factor = math.exp(-decay_lambda * age_days)
            r.score *= decay_factor
    return results


def _tokenize(text: str) -> Set[str]:
    tokens = set()
    current = []
    for ch in text.lower():
        if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
            current.append(ch)
        else:
            if current:
                tokens.add("".join(current))
                current = []
    if current:
        tokens.add("".join(current))
    cjk_tokens = set()
    for token in list(tokens):
        if any('\u4e00' <= ch <= '\u9fff' for ch in token):
            for i in range(len(token)):
                cjk_tokens.add(token[i])
                if i + 1 < len(token):
                    cjk_tokens.add(token[i:i+2])
    tokens.update(cjk_tokens)
    return tokens


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def apply_mmr(
    results: List[MemorySearchResult],
    config: MMRConfig,
    max_results: int = 10,
) -> List[MemorySearchResult]:
    if not config.enabled or len(results) <= max_results:
        return results
    lam = config.lambda_param
    selected: List[MemorySearchResult] = []
    remaining = list(results)
    tokenized: Dict[str, Set[str]] = {}
    for r in results:
        tokenized[r.chunk.id] = _tokenize(r.chunk.text)
    if remaining:
        selected.append(remaining.pop(0))
    while len(selected) < max_results and remaining:
        best_idx = 0
        best_score = -float("inf")
        for i, candidate in enumerate(remaining):
            relevance = candidate.score
            max_sim = 0.0
            cand_tokens = tokenized.get(candidate.chunk.id, set())
            for sel in selected:
                sel_tokens = tokenized.get(sel.chunk.id, set())
                sim = _jaccard_similarity(cand_tokens, sel_tokens)
                max_sim = max(max_sim, sim)
            mmr_score = lam * relevance - (1 - lam) * max_sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        selected.append(remaining.pop(best_idx))
    return selected


def merge_hybrid_results(
    vector_results: List[MemorySearchResult],
    text_results: List[MemorySearchResult],
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
) -> List[MemorySearchResult]:
    merged: Dict[str, MemorySearchResult] = {}
    for r in vector_results:
        merged[r.chunk.id] = MemorySearchResult(
            chunk=r.chunk,
            score=0.0,
            vector_score=r.score,
            text_score=0.0,
        )
    for r in text_results:
        if r.chunk.id in merged:
            merged[r.chunk.id].text_score = r.score
        else:
            merged[r.chunk.id] = MemorySearchResult(
                chunk=r.chunk,
                score=0.0,
                vector_score=0.0,
                text_score=r.score,
            )
    for r in merged.values():
        r.score = vector_weight * r.vector_score + text_weight * r.text_score
    return sorted(merged.values(), key=lambda x: x.score, reverse=True)


def bm25_rank_to_score(rank: float) -> float:
    if rank < 0:
        relevance = abs(rank)
        return relevance / (1.0 + relevance)
    return 1.0 / (1.0 + rank)
