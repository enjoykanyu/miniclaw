import asyncio
import json
import logging

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


def _flatten_config(cfg: dict, prefix: str = "") -> dict:
    result = {}
    for key, value in cfg.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_config(value, full_key))
        else:
            result[full_key] = value
    return result


def classify_config_change(
        old_cfg: dict,
        new_cfg: dict,
) -> dict:
    flat_old = _flatten_config(old_cfg)
    flat_new = _flatten_config(new_cfg)
    all_keys = set(flat_old.keys()) | set(flat_new.keys())
    changed_keys = []
    for key in sorted(all_keys):
        old_val = flat_old.get(key)
        new_val = flat_new.get(key)
        if old_val != new_val:
            changed_keys.append(key)

    if not changed_keys:
        return {"type": "no-change"}

    has_restart_required = any(
        key in RESTART_REQUIRED_KEYS or any(
            key.startswith(rk + ".") for rk in RESTART_REQUIRED_KEYS
        )
        for key in changed_keys
    )

    if has_restart_required:
        return {"type": "restart-required", "keys": changed_keys}

    return {"type": "hot-reloaded", "keys": changed_keys}


async def handle_config_reload(
        old_cfg: dict,
        new_cfg: dict,
        runtime: dict,
) -> None:
    result = classify_config_change(old_cfg, new_cfg)

    if result["type"] == "no-change":
        return

    if result["type"] == "hot-reloaded":
        runtime["cfg"] = new_cfg
        for key in result["keys"]:
            if key == "gateway.logLevel":
                level = new_cfg.get("gateway", {}).get("logLevel", "info")
                logging.getLogger().setLevel(level.upper())
                print(f"[config-reload] logLevel updated to {level}")
            elif key == "gateway.maxPayloadBytes":
                print(f"[config-reload] maxPayloadBytes updated to {new_cfg.get('gateway', {}).get('maxPayloadBytes')}")
        print(f"[config-reload] hot-reloaded keys: {result['keys']}")
        return

    if result["type"] == "restart-required":
        runtime["cfg"] = new_cfg
        print(f"[config-reload] restart required for keys: {result['keys']}")
        return


async def _watch_config_reload(
        config_path: str,
        runtime: dict,
) -> None:
    while True:
        try:
            await asyncio.sleep(5)
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    new_cfg = json.load(f)
            except FileNotFoundError:
                continue
            except json.JSONDecodeError:
                continue
            except OSError:
                continue

            old_cfg = runtime.get("cfg", {})
            if new_cfg != old_cfg:
                await handle_config_reload(old_cfg, new_cfg, runtime)
        except asyncio.CancelledError:
            return
        except Exception:
            continue
