"""
MiniClaw Permission System

借鉴 cc-haha 的三层权限规则 (allow/deny/ask) + 多种权限模式

权限检查流程:
1. 检查 deny 规则 → 直接拒绝
2. 检查 ask 规则 → 需要确认
3. 工具自身 check_permissions() → 工具级权限
4. bypass 模式 → 直接放行
5. allow 规则 → 直接放行
6. 默认 → ask

规则来源优先级:
  user_settings > project_settings > local_settings > default
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable, Awaitable

from miniclaw.tools.base import (
    Tool, PermissionBehavior, PermissionMode, PermissionDecision, ToolCategory
)

logger = logging.getLogger(__name__)


class RuleSource(str, Enum):
    USER_SETTINGS = "user_settings"
    PROJECT_SETTINGS = "project_settings"
    LOCAL_SETTINGS = "local_settings"
    CLI_ARG = "cli_arg"
    SESSION = "session"
    DEFAULT = "default"


@dataclass
class PermissionRule:
    tool_pattern: str
    behavior: PermissionBehavior
    source: RuleSource = RuleSource.DEFAULT
    content_pattern: Optional[str] = None
    description: str = ""

    _compiled_tool: Optional[re.Pattern] = field(default=None, repr=False)
    _compiled_content: Optional[re.Pattern] = field(default=None, repr=False)

    def matches_tool(self, tool_name: str) -> bool:
        if self._compiled_tool is None:
            try:
                self._compiled_tool = re.compile(self.tool_pattern)
            except re.error:
                self._compiled_tool = re.compile(re.escape(self.tool_pattern))
        return bool(self._compiled_tool.match(tool_name))

    def matches_content(self, args: dict[str, Any]) -> bool:
        if self.content_pattern is None:
            return True
        if self._compiled_content is None:
            try:
                self._compiled_content = re.compile(self.content_pattern)
            except re.error:
                self._compiled_content = re.compile(re.escape(self.content_pattern))
        for val in args.values():
            if isinstance(val, str) and self._compiled_content.search(val):
                return True
        return False


PROTECTED_PATHS = [
    re.compile(r"^/etc/"),
    re.compile(r"^/sys/"),
    re.compile(r"^/proc/"),
    re.compile(r"/\.ssh/"),
    re.compile(r"/\.gnupg/"),
    re.compile(r"/\.env$"),
    re.compile(r"/\.aws/"),
]

DANGEROUS_SHELL_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\bmkfs\."),
    re.compile(r"\bformat\s+[A-Z]:"),
    re.compile(r">\s*/dev/sd"),
    re.compile(r"\bchmod\s+-R\s+777\s+/"),
    re.compile(r"\bcurl\s+.*\|\s*sh"),
    re.compile(r"\bwget\s+.*\|\s*sh"),
    re.compile(r"\bgit\s+push\s+--force"),
    re.compile(r"\bgit\s+reset\s+--hard"),
]

DANGEROUS_WRITE_PATTERNS = [
    re.compile(r"/\.git/"),
    re.compile(r"/\.claude/"),
    re.compile(r"/__pycache__/"),
]


class PermissionManager:
    """
    权限管理器

    三层规则: deny > ask > allow
    五种模式: default / plan / auto / bypass / dont_ask
    """

    def __init__(self):
        self._deny_rules: list[PermissionRule] = []
        self._ask_rules: list[PermissionRule] = []
        self._allow_rules: list[PermissionRule] = []
        self._mode: PermissionMode = PermissionMode.DEFAULT
        self._confirm_callback: Optional[Callable[[str], Awaitable[bool]]] = None
        self._denied_count: int = 0
        self._max_consecutive_denies: int = 5

    @property
    def mode(self) -> PermissionMode:
        return self._mode

    @mode.setter
    def mode(self, mode: PermissionMode) -> None:
        self._mode = mode
        logger.info(f"Permission mode changed to: {mode.value}")

    def set_confirm_callback(self, callback: Callable[[str], Awaitable[bool]]) -> None:
        self._confirm_callback = callback

    def add_rule(self, rule: PermissionRule) -> None:
        if rule.behavior == PermissionBehavior.DENY:
            self._deny_rules.append(rule)
        elif rule.behavior == PermissionBehavior.ASK:
            self._ask_rules.append(rule)
        elif rule.behavior == PermissionBehavior.ALLOW:
            self._allow_rules.append(rule)

    def add_deny_rule(self, tool_pattern: str, content_pattern: str | None = None,
                      source: RuleSource = RuleSource.DEFAULT) -> None:
        self.add_rule(PermissionRule(
            tool_pattern=tool_pattern,
            behavior=PermissionBehavior.DENY,
            source=source,
            content_pattern=content_pattern,
        ))

    def add_allow_rule(self, tool_pattern: str, content_pattern: str | None = None,
                       source: RuleSource = RuleSource.DEFAULT) -> None:
        self.add_rule(PermissionRule(
            tool_pattern=tool_pattern,
            behavior=PermissionBehavior.ALLOW,
            source=source,
            content_pattern=content_pattern,
        ))

    def add_ask_rule(self, tool_pattern: str, content_pattern: str | None = None,
                     source: RuleSource = RuleSource.DEFAULT) -> None:
        self.add_rule(PermissionRule(
            tool_pattern=tool_pattern,
            behavior=PermissionBehavior.ASK,
            source=source,
            content_pattern=content_pattern,
        ))

    def load_default_rules(self) -> None:
        self.add_deny_rule(".*", content_pattern=r"rm\s+-rf\s+/", source=RuleSource.DEFAULT)
        self.add_deny_rule(".*", content_pattern=r"dd\s+if=", source=RuleSource.DEFAULT)
        self.add_deny_rule(".*", content_pattern=r"curl.*\|\s*sh", source=RuleSource.DEFAULT)
        self.add_ask_rule("bash", source=RuleSource.DEFAULT)
        self.add_ask_rule("write_file", source=RuleSource.DEFAULT)
        self.add_ask_rule("mcp__.*", source=RuleSource.DEFAULT)
        self.add_allow_rule("read_file", source=RuleSource.DEFAULT)
        self.add_allow_rule("list_files", source=RuleSource.DEFAULT)
        self.add_allow_rule("grep_search", source=RuleSource.DEFAULT)

    async def check(self, tool: Tool, args: dict[str, Any]) -> PermissionDecision:
        """
        完整权限检查流程

        优先级:
        1. deny 规则 → DENY
        2. ask 规则 → ASK
        3. 工具自身 check_permissions → 工具级决策
        4. 安全路径检查 → DENY
        5. bypass 模式 → ALLOW
        6. allow 规则 → ALLOW
        7. plan 模式只读检查 → DENY/ALLOW
        8. 默认 → ASK
        """
        tool_name = tool.name

        # Step 1: deny 规则
        for rule in self._deny_rules:
            if rule.matches_tool(tool_name) and rule.matches_content(args):
                return PermissionDecision(
                    behavior=PermissionBehavior.DENY,
                    reason=f"Denied by rule: {rule.tool_pattern}",
                    tool_name=tool_name,
                    rule_source=rule.source.value,
                )

        # Step 2: ask 规则
        for rule in self._ask_rules:
            if rule.matches_tool(tool_name) and rule.matches_content(args):
                decision = await self._resolve_ask(
                    tool_name, args,
                    reason=f"Requires confirmation by rule: {rule.tool_pattern}",
                    source=rule.source.value,
                )
                if decision.behavior == PermissionBehavior.DENY:
                    return decision

        # Step 3: 工具自身权限检查
        tool_decision = tool.check_permissions(args, self._mode)
        if tool_decision.behavior == PermissionBehavior.DENY:
            return tool_decision
        if tool_decision.behavior == PermissionBehavior.ASK:
            decision = await self._resolve_ask(
                tool_name, args,
                reason=tool_decision.reason,
                source=tool_decision.rule_source or "tool",
            )
            if decision.behavior == PermissionBehavior.DENY:
                return decision

        # Step 4: 安全路径检查
        path_check = self._check_protected_paths(tool, args)
        if path_check is not None:
            return path_check

        # Step 5: bypass 模式
        if self._mode == PermissionMode.BYPASS:
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                reason="Bypass mode",
                tool_name=tool_name,
                rule_source="mode",
            )

        # Step 6: allow 规则
        for rule in self._allow_rules:
            if rule.matches_tool(tool_name) and rule.matches_content(args):
                return PermissionDecision(
                    behavior=PermissionBehavior.ALLOW,
                    reason=f"Allowed by rule: {rule.tool_pattern}",
                    tool_name=tool_name,
                    rule_source=rule.source.value,
                )

        # Step 7: plan 模式只读检查
        if self._mode == PermissionMode.PLAN:
            if not getattr(tool, "READONLY", True):
                return PermissionDecision(
                    behavior=PermissionBehavior.DENY,
                    reason="Plan mode only allows readonly tools",
                    tool_name=tool_name,
                    rule_source="mode",
                )
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                reason="Plan mode readonly tool",
                tool_name=tool_name,
                rule_source="mode",
            )

        # Step 8: 默认 ask
        return await self._resolve_ask(
            tool_name, args,
            reason="No matching rule, defaulting to ask",
            source="default",
        )

    def _check_protected_paths(self, tool: Tool, args: dict[str, Any]) -> Optional[PermissionDecision]:
        if tool.category in (ToolCategory.FILE_WRITE, ToolCategory.SHELL):
            for val in args.values():
                if not isinstance(val, str):
                    continue
                for pattern in PROTECTED_PATHS:
                    if pattern.search(val):
                        return PermissionDecision(
                            behavior=PermissionBehavior.DENY,
                            reason=f"Protected path: {val}",
                            tool_name=tool.name,
                            rule_source="security",
                        )
        if tool.category == ToolCategory.SHELL:
            cmd = args.get("command", "")
            for pattern in DANGEROUS_SHELL_PATTERNS:
                if pattern.search(cmd):
                    return PermissionDecision(
                        behavior=PermissionBehavior.DENY,
                        reason=f"Dangerous shell command: {cmd[:50]}",
                        tool_name=tool.name,
                        rule_source="security",
                    )
        if tool.category == ToolCategory.FILE_WRITE:
            path = args.get("path", "")
            for pattern in DANGEROUS_WRITE_PATTERNS:
                if pattern.search(path):
                    return PermissionDecision(
                        behavior=PermissionBehavior.ASK,
                        reason=f"Writing to protected path: {path}",
                        tool_name=tool.name,
                        rule_source="security",
                    )
        return None

    async def _resolve_ask(
        self,
        tool_name: str,
        args: dict[str, Any],
        reason: str,
        source: str,
    ) -> PermissionDecision:
        if self._mode == PermissionMode.AUTO:
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                reason=f"Auto-approved (ask rule: {reason})",
                tool_name=tool_name,
                rule_source=source,
            )

        if self._mode == PermissionMode.DONT_ASK:
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                reason=f"Denied without asking (ask rule: {reason})",
                tool_name=tool_name,
                rule_source=source,
            )

        if self._confirm_callback:
            approved = await self._confirm_callback(
                f"Tool: {tool_name}\nReason: {reason}\nArgs: {args}\nAllow? (y/n): "
            )
            if not approved:
                self._denied_count += 1
                if self._denied_count >= self._max_consecutive_denies:
                    logger.warning(
                        f"Too many consecutive denials ({self._denied_count}), "
                        f"switching to dont_ask mode"
                    )
                    self._mode = PermissionMode.DONT_ASK
                return PermissionDecision(
                    behavior=PermissionBehavior.DENY,
                    reason="User denied",
                    tool_name=tool_name,
                    rule_source="user",
                )
            self._denied_count = 0
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                reason="User approved",
                tool_name=tool_name,
                rule_source="user",
            )

        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            reason=reason,
            tool_name=tool_name,
            rule_source=source,
        )


permission_manager = PermissionManager()
