HOT_RELOADABLE_KEYS = {
    "gateway.logLevel",
    "gateway.maxPayloadBytes",
    "gateway.broadcast.bufferSize",
    "gateway.cron",
}

RESTART_REQUIRED_KEYS = {
    "gateway.port",
    "gateway.bind",
    "gateway.auth",
    "gateway.tls",
}

def classify_config_change(
        old_cfg: dict,
        new_cfg: dict,
) -> dict:
    """对应 classifyConfigChange: 分类配置变更

    比较新旧配置，返回变更类型：
    - {"type": "no-change"} — 无变更
    - {"type": "hot-reloaded", "keys": [...]} — 可热更新
    - {"type": "restart-required", "keys": [...]} — 需重启
    """
    raise NotImplementedError("TODO: 后续章节实现")

async def handle_config_reload(
        old_cfg: dict,
        new_cfg: dict,
        runtime: dict,
) -> None:
    """对应 handleConfigReload: 执行配置重载

    根据分类结果执行不同操作：
    - no-change: 什么都不做
    - hot-reloaded: 调用 runtime.apply_hot_reload()
    - restart-required: 调用 runtime.request_graceful_restart()
    """
    raise NotImplementedError("TODO: 后续章节实现")

async def _watch_config_reload(
        config_path: str,
        runtime: dict,
) -> None:
    """监听配置文件变更，触发热重载

    使用 watchfiles 库监听配置文件变更，
    变更时读取新配置 → classify → handle。
    """
    raise NotImplementedError("TODO: 后续章节实现")