import secrets
import os
import asyncio
from dataclasses import dataclass
from typing import Optional

WEAK_TOKENS = {"password", "123456", "admin", "token", "secret", "openclaw"}

@dataclass
class StartupAuthResult:
    cfg: dict
    auth: dict
    generated_token: Optional[str] = None
    persisted_generated_token: bool = False

async def ensure_gateway_startup_auth(
        cfg: dict,
        env: Optional[dict] = None,
        auth_override: Optional[dict] = None,
        persist: bool = False,
) -> StartupAuthResult:
    """对应 ensureGatewayStartupAuth(): 认证引导"""

    if env is None:
        env = dict(os.environ)

    # 并行解析 Secret 引用 (Promise.all → asyncio.gather)
    resolved_token, resolved_password = await asyncio.gather(
        _resolve_gateway_token_secret_ref_value(cfg, env),
        _resolve_gateway_password_secret_ref_value(cfg, env),
    )

    # 构建认证覆盖
    override = dict(auth_override or {})
    if resolved_token:
        override["token"] = resolved_token
    if resolved_password:
        override["password"] = resolved_password

    # 从配置解析认证
    resolved = _resolve_gateway_auth_from_config(cfg, env, override)

    # 已有 token → 直接返回
    if resolved.get("mode") != "token" or resolved.get("token", "").strip():
        _assert_gateway_auth_not_known_weak(resolved)
        _assert_hooks_token_separate(cfg, resolved)
        return StartupAuthResult(cfg=cfg, auth=resolved)

    # ★ 生成随机 token ★
    generated_token = secrets.token_hex(24)

    # 更新配置
    next_cfg = {**cfg}
    next_cfg.setdefault("gateway", {})
    next_cfg["gateway"].setdefault("auth", {})
    next_cfg["gateway"]["auth"] = {
        **next_cfg["gateway"]["auth"],
        "mode": "token",
        "token": generated_token,
    }

    # 持久化
    if persist:
        await _replace_config_file(next_cfg)

    # 重新解析 + 断言
    next_auth = _resolve_gateway_auth_from_config(next_cfg, env, override)
    _assert_gateway_auth_not_known_weak(next_auth)
    _assert_hooks_token_separate(next_cfg, next_auth)

    return StartupAuthResult(
        cfg=next_cfg, auth=next_auth,
        generated_token=generated_token,
        persisted_generated_token=persist,
    )

def _assert_gateway_auth_not_known_weak(auth: dict) -> None:
    """弱密码检测"""
    token = auth.get("token", "")
    if token.lower() in WEAK_TOKENS:
        raise ValueError(
            f"Gateway auth token is weak ('{token}'). "
            f"Use a strong random token."
        )

def _assert_hooks_token_separate(cfg: dict, auth: dict) -> None:
    """Hooks Token 分离检查"""
    hooks_token = cfg.get("hooks", {}).get("token", "")
    gateway_token = auth.get("token", "")
    if hooks_token and hooks_token == gateway_token:
        raise ValueError(
            "Hooks token must differ from gateway auth token"
        )

async def _resolve_gateway_token_secret_ref_value(cfg, env):
    return env.get("OPENCLAW_GATEWAY_AUTH_TOKEN")

async def _resolve_gateway_password_secret_ref_value(cfg, env):
    return env.get("OPENCLAW_GATEWAY_AUTH_PASSWORD")

def _resolve_gateway_auth_from_config(cfg, env, override=None):
    auth = cfg.get("gateway", {}).get("auth", {})
    result = {**auth, **(override or {})}
    return result

async def _replace_config_file(cfg):
    pass