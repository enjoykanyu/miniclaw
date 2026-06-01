"""
Tool Loop Detection & Circuit Breaker

对标 OpenClaw 的 tool-loop-detection.ts，实现 5 种检测器：
  - generic_repeat: 通用重复检测
  - unknown_tool_repeat: 未知工具重复调用
  - known_poll_no_progress: 轮询无进展
  - global_circuit_breaker: 全局断路器
  - ping_pong: 乒乓式交替调用

阈值体系：
  - Warning: 注入警告消息
  - Critical: 阻断执行
  - Breaker: 强制终止
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json

from loguru import logger


class LoopSeverity(str, Enum):
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"
    BREAKER = "breaker"


class LoopDetectorKind(str, Enum):
    GENERIC_REPEAT = "generic_repeat"
    UNKNOWN_TOOL_REPEAT = "unknown_tool_repeat"
    KNOWN_POLL_NO_PROGRESS = "known_poll_no_progress"
    GLOBAL_CIRCUIT_BREAKER = "global_circuit_breaker"
    PING_PONG = "ping_pong"


@dataclass
class LoopDetectionResult:
    detected: bool = False
    severity: LoopSeverity = LoopSeverity.NONE
    detector: LoopDetectorKind = LoopDetectorKind.GENERIC_REPEAT
    message: str = ""
    suggestion: str = ""


@dataclass
class ToolCallFingerprint:
    tool_name: str
    args_hash: str
    timestamp: str
    iteration: int


def _hash_args(args: Dict[str, Any]) -> str:
    try:
        canonical = json.dumps(args, sort_keys=True, default=str)
        return hashlib.md5(canonical.encode()).hexdigest()[:12]
    except (TypeError, ValueError):
        return hashlib.md5(str(args).encode()).hexdigest()[:12]


@dataclass
class LoopDetectorConfig:
    generic_repeat_window: int = 5
    generic_repeat_threshold: int = 3
    unknown_tool_repeat_window: int = 4
    unknown_tool_repeat_threshold: int = 3
    poll_no_progress_window: int = 6
    poll_no_progress_threshold: int = 4
    ping_pong_window: int = 6
    ping_pong_threshold: int = 3
    global_circuit_breaker_limit: int = 30
    warning_threshold: int = 10
    critical_threshold: int = 20


class LoopDetector:
    """
    工具循环检测器

    对标 OpenClaw 的 createToolLoopDetectors，
    在每次工具调用前检测是否陷入死循环。
    """

    def __init__(self, config: Optional[LoopDetectorConfig] = None):
        self.config = config or LoopDetectorConfig()
        self._fingerprints: List[ToolCallFingerprint] = []
        self._total_calls: int = 0
        self._warning_injected: bool = False

    def observe(self, tool_name: str, args: Dict[str, Any], iteration: int) -> LoopDetectionResult:
        self._total_calls += 1
        fingerprint = ToolCallFingerprint(
            tool_name=tool_name,
            args_hash=_hash_args(args),
            timestamp=datetime.now().isoformat(),
            iteration=iteration,
        )
        self._fingerprints.append(fingerprint)

        breaker_result = self._check_global_circuit_breaker()
        if breaker_result.detected:
            return breaker_result

        critical_result = self._check_generic_repeat(fingerprint)
        if critical_result.detected:
            return critical_result

        ping_pong_result = self._check_ping_pong()
        if ping_pong_result.detected:
            return ping_pong_result

        poll_result = self._check_poll_no_progress()
        if poll_result.detected:
            return poll_result

        if self._total_calls >= self.config.warning_threshold and not self._warning_injected:
            self._warning_injected = True
            return LoopDetectionResult(
                detected=True,
                severity=LoopSeverity.WARNING,
                detector=LoopDetectorKind.GLOBAL_CIRCUIT_BREAKER,
                message=f"工具调用已达 {self._total_calls} 次，请注意是否存在循环调用",
                suggestion="考虑简化任务或直接给出当前最佳答案",
            )

        return LoopDetectionResult(detected=False)

    def _check_global_circuit_breaker(self) -> LoopDetectionResult:
        if self._total_calls >= self.config.global_circuit_breaker_limit:
            return LoopDetectionResult(
                detected=True,
                severity=LoopSeverity.BREAKER,
                detector=LoopDetectorKind.GLOBAL_CIRCUIT_BREAKER,
                message=f"全局断路器触发：工具调用已达 {self._total_calls} 次上限",
                suggestion="强制终止循环，返回当前最佳结果",
            )
        if self._total_calls >= self.config.critical_threshold:
            return LoopDetectionResult(
                detected=True,
                severity=LoopSeverity.CRITICAL,
                detector=LoopDetectorKind.GLOBAL_CIRCUIT_BREAKER,
                message=f"工具调用次数 {self._total_calls} 接近断路器阈值",
                suggestion="请立即总结当前结果并结束",
            )
        return LoopDetectionResult(detected=False)

    def _check_generic_repeat(self, current: ToolCallFingerprint) -> LoopDetectionResult:
        window = self.config.generic_repeat_window
        threshold = self.config.generic_repeat_threshold

        recent = self._fingerprints[-window:] if len(self._fingerprints) >= threshold else self._fingerprints

        same_calls = [
            fp for fp in recent
            if fp.tool_name == current.tool_name and fp.args_hash == current.args_hash
        ]

        if len(same_calls) >= threshold:
            return LoopDetectionResult(
                detected=True,
                severity=LoopSeverity.CRITICAL,
                detector=LoopDetectorKind.GENERIC_REPEAT,
                message=f"检测到工具 '{current.tool_name}' 重复调用 {len(same_calls)} 次（相同参数）",
                suggestion="请更换参数或使用不同工具，避免重复操作",
            )

        name_only_repeats = [fp for fp in recent if fp.tool_name == current.tool_name]
        if len(name_only_repeats) >= threshold + 2:
            return LoopDetectionResult(
                detected=True,
                severity=LoopSeverity.WARNING,
                detector=LoopDetectorKind.GENERIC_REPEAT,
                message=f"检测到工具 '{current.tool_name}' 频繁调用 {len(name_only_repeats)} 次",
                suggestion="请确认是否需要继续调用此工具",
            )

        return LoopDetectionResult(detected=False)

    def _check_ping_pong(self) -> LoopDetectionResult:
        window = self.config.ping_pong_window
        threshold = self.config.ping_pong_threshold

        if len(self._fingerprints) < 4:
            return LoopDetectionResult(detected=False)

        recent = self._fingerprints[-window:]
        if len(recent) < 4:
            return LoopDetectionResult(detected=False)

        tool_sequence = [fp.tool_name for fp in recent]

        ping_pong_count = 0
        for i in range(len(tool_sequence) - 1):
            if i + 2 < len(tool_sequence):
                if (tool_sequence[i] == tool_sequence[i + 2] and
                        tool_sequence[i] != tool_sequence[i + 1]):
                    ping_pong_count += 1

        if ping_pong_count >= threshold:
            pair = f"{tool_sequence[-2]} <-> {tool_sequence[-1]}" if len(tool_sequence) >= 2 else ""
            return LoopDetectionResult(
                detected=True,
                severity=LoopSeverity.CRITICAL,
                detector=LoopDetectorKind.PING_PONG,
                message=f"检测到乒乓式交替调用: {pair}（交替 {ping_pong_count} 次）",
                suggestion="请打破交替模式，尝试不同的解决策略",
            )

        return LoopDetectionResult(detected=False)

    def _check_poll_no_progress(self) -> LoopDetectionResult:
        window = self.config.poll_no_progress_window
        threshold = self.config.poll_no_progress_threshold

        if len(self._fingerprints) < threshold:
            return LoopDetectionResult(detected=False)

        recent = self._fingerprints[-window:]

        poll_tools = {}
        for fp in recent:
            if fp.tool_name not in poll_tools:
                poll_tools[fp.tool_name] = []
            poll_tools[fp.tool_name].append(fp.args_hash)

        for tool_name, hashes in poll_tools.items():
            if len(hashes) >= threshold:
                unique_hashes = len(set(hashes))
                if unique_hashes <= 2:
                    return LoopDetectionResult(
                        detected=True,
                        severity=LoopSeverity.WARNING,
                        detector=LoopDetectorKind.KNOWN_POLL_NO_PROGRESS,
                        message=f"检测到工具 '{tool_name}' 轮询无进展（{len(hashes)} 次调用，仅 {unique_hashes} 种参数）",
                        suggestion="轮询结果可能不会变化，请基于当前结果继续",
                    )

        return LoopDetectionResult(detected=False)

    def reset(self):
        self._fingerprints.clear()
        self._total_calls = 0
        self._warning_injected = False

    @property
    def total_calls(self) -> int:
        return self._total_calls

    def get_summary(self) -> Dict[str, Any]:
        tool_counts: Dict[str, int] = {}
        for fp in self._fingerprints:
            tool_counts[fp.tool_name] = tool_counts.get(fp.tool_name, 0) + 1
        return {
            "total_calls": self._total_calls,
            "unique_tools": len(tool_counts),
            "tool_counts": tool_counts,
            "warning_injected": self._warning_injected,
        }


class IdleTimeoutBreaker:
    """
    空闲超时断路器

    对标 OpenClaw 的 createIdleTimeoutBreakerState，
    防止连续空闲超时导致的成本失控。
    """

    def __init__(self, max_consecutive_idle: int = 3):
        self._max_consecutive_idle = max_consecutive_idle
        self._consecutive_idle: int = 0
        self._tripped: bool = False

    def step(self, idle_timed_out: bool, has_progress: bool) -> bool:
        if idle_timed_out and not has_progress:
            self._consecutive_idle += 1
        else:
            self._consecutive_idle = 0

        if self._consecutive_idle >= self._max_consecutive_idle:
            self._tripped = True
            logger.warning(
                f"IdleTimeoutBreaker tripped: {self._consecutive_idle} consecutive idle timeouts"
            )

        return self._tripped

    @property
    def tripped(self) -> bool:
        return self._tripped

    def reset(self):
        self._consecutive_idle = 0
        self._tripped = False


class PostCompactionLoopGuard:
    """
    压缩后循环保卫

    对标 OpenClaw 的 createPostCompactionLoopGuard，
    防止上下文压缩后陷入无限循环。
    """

    def __init__(self, max_post_compaction_repeats: int = 3):
        self._max_repeats = max_post_compaction_repeats
        self._armed: bool = False
        self._post_compaction_calls: int = 0
        self._tripped: bool = False

    def arm(self):
        self._armed = True
        self._post_compaction_calls = 0

    def observe(self, tool_name: str, args: Dict[str, Any]) -> bool:
        if not self._armed:
            return False

        self._post_compaction_calls += 1

        if self._post_compaction_calls >= self._max_repeats:
            self._tripped = True
            logger.warning(
                f"PostCompactionLoopGuard tripped: {self._post_compaction_calls} calls after compaction"
            )

        return self._tripped

    @property
    def tripped(self) -> bool:
        return self._tripped

    @property
    def armed(self) -> bool:
        return self._armed

    def reset(self):
        self._armed = False
        self._post_compaction_calls = 0
        self._tripped = False
