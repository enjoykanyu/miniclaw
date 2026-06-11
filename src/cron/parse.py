"""
Cron 表达式解析器

对应 OpenClaw 的 cron 调度功能：
  - 解析标准 5 字段 cron 表达式（分 时 日 月 周）
  - 计算下一次运行时间
  - 不依赖外部库，纯 Python 实现
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger


# 每个字段的范围和别名
_FIELD_RANGES = [
    (0, 59),   # 分钟
    (0, 23),   # 小时
    (1, 31),   # 日
    (1, 12),   # 月
    (0, 6),    # 周几（0=周日）
]

_MONTH_ALIASES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DOW_ALIASES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3,
    "thu": 4, "fri": 5, "sat": 6,
}


def _parse_field(field_str: str, field_index: int) -> set[int]:
    """解析单个 cron 字段为允许值的集合

    支持的格式：
    - *: 所有值
    - 5: 特定值
    - 1,3,5: 列表
    - 1-5: 范围
    - */5: 步长
    - 1-10/2: 范围+步长
    """
    lo, hi = _FIELD_RANGES[field_index]
    result: set[int] = set()

    # 替换别名
    field_str = field_str.lower()
    if field_index == 3:  # 月
        for alias, val in _MONTH_ALIASES.items():
            field_str = field_str.replace(alias, str(val))
    elif field_index == 4:  # 周几
        for alias, val in _DOW_ALIASES.items():
            field_str = field_str.replace(alias, str(val))

    for part in field_str.split(","):
        part = part.strip()
        if part == "*":
            step = 1
            result.update(range(lo, hi + 1, step))
        elif "/" in part:
            range_part, step_str = part.split("/", 1)
            step = int(step_str)
            if range_part == "*":
                result.update(range(lo, hi + 1, step))
            elif "-" in range_part:
                start, end = range_part.split("-", 1)
                result.update(range(int(start), int(end) + 1, step))
            else:
                result.update(range(int(range_part), hi + 1, step))
        elif "-" in part:
            start, end = part.split("-", 1)
            result.update(range(int(start), int(end) + 1))
        else:
            val = int(part)
            result.add(val)

    # 过滤超出范围的值
    result = {v for v in result if lo <= v <= hi}
    return result


def parse_cron_expression(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """解析标准 5 字段 cron 表达式

    格式: 分 时 日 月 周

    Args:
        expr: cron 表达式字符串

    Returns:
        (minutes, hours, days, months, dows) 五个允许值集合

    Raises:
        ValueError: 表达式格式错误
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"Cron expression must have 5 fields, got {len(parts)}: {expr!r}"
        )

    fields = []
    for i, part in enumerate(parts):
        try:
            field_values = _parse_field(part, i)
            if not field_values:
                raise ValueError(f"Empty field at position {i}")
            fields.append(field_values)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid cron field at position {i}: {part!r} ({e})") from e

    return tuple(fields)  # type: ignore


def calculate_next_run(
    expr: str,
    from_time: Optional[datetime] = None,
) -> datetime:
    """计算 cron 表达式的下一次运行时间

    Args:
        expr: cron 表达式
        from_time: 起始时间（默认为当前时间）

    Returns:
        下一次运行时间

    Raises:
        ValueError: 表达式格式错误
    """
    minutes, hours, days, months, dows = parse_cron_expression(expr)

    if from_time is None:
        from_time = datetime.now()

    # 从下一分钟开始搜索
    candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # 最多搜索 4 年（覆盖闰年场景）
    max_iterations = 4 * 366 * 24 * 60
    for _ in range(max_iterations):
        if (candidate.month in months
                and candidate.day in days
                and candidate.weekday() in _py_weekday_to_cron(dows)
                and candidate.hour in hours
                and candidate.minute in minutes):
            return candidate

        # 递增：优先跳到下一个可能匹配的时间
        if candidate.month not in months:
            # 跳到下个月
            if candidate.month == 12:
                candidate = candidate.replace(year=candidate.year + 1, month=1, day=1, hour=0, minute=0)
            else:
                candidate = candidate.replace(month=candidate.month + 1, day=1, hour=0, minute=0)
        elif candidate.day not in days or candidate.weekday() not in _py_weekday_to_cron(dows):
            candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
        elif candidate.hour not in hours:
            candidate = candidate.replace(minute=0) + timedelta(hours=1)
        else:
            candidate += timedelta(minutes=1)

    raise ValueError(f"Could not find next run time for expression: {expr!r}")


def _py_weekday_to_cron(dows: set[int]) -> set[int]:
    """将 cron 周几（0=周日）转换为 Python weekday（0=周一）"""
    # cron: 0=Sun,1=Mon,...,6=Sat
    # Python: 0=Mon,1=Tue,...,6=Sun
    mapping = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    return {mapping[d] for d in dows}
