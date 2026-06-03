from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class MemorySource(str, Enum):
    MEMORY = "memory"
    SESSIONS = "sessions"


@dataclass
class MemoryChunk:
    id: str
    path: str
    source: MemorySource = MemorySource.MEMORY
    start_line: int = 0
    end_line: int = 0
    text: str = ""
    model: str = ""
    hash: str = ""
    embedding: Optional[List[float]] = None
    updated_at: float = 0.0


@dataclass
class MemorySearchResult:
    chunk: MemoryChunk
    score: float = 0.0
    vector_score: float = 0.0
    text_score: float = 0.0


@dataclass
class MemoryProviderStatus:
    available: bool = False
    vector_enabled: bool = False
    fts_enabled: bool = False
    embedding_model: str = ""
    total_chunks: int = 0
    total_files: int = 0
    db_path: str = ""


@dataclass
class HybridSearchConfig:
    enabled: bool = True
    vector_weight: float = 0.7
    text_weight: float = 0.3
    candidate_multiplier: int = 4


@dataclass
class TemporalDecayConfig:
    enabled: bool = False
    half_life_days: float = 30.0


@dataclass
class MMRConfig:
    enabled: bool = False
    lambda_param: float = 0.7


@dataclass
class MemoryFlushPlan:
    soft_threshold_tokens: int = 4000
    force_flush_transcript_bytes: int = 2 * 1024 * 1024
    reserve_tokens_floor: int = 20000
    model: Optional[str] = None
    relative_path: str = ""
    prompt: str = ""
    system_prompt: str = ""


CANONICAL_ROOT_MEMORY_FILENAME = "MEMORY.md"
MEMORY_DIR_NAME = "memory"
DREAMS_FILENAME = "dreams.md"
