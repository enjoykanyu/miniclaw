"""
MiniClaw Utility Functions
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict
from datetime import datetime

from miniclaw.config.settings import settings


def ensure_dir(path: str) -> Path:
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def load_prompt_template(prompt_name: str) -> Dict[str, Any]:
    prompt_dir = Path(__file__).parent.parent / "config" / "prompts"
    prompt_file = prompt_dir / f"{prompt_name}.yaml"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_name}")
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_datetime(dt: datetime = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def parse_datetime(dt_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    return datetime.strptime(dt_str, fmt)


def get_weekday_name(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return weekdays[dt.weekday()]


def init_data_dirs():
    for dir_path in [settings.DATA_DIR, settings.EXCEL_DIR, settings.KNOWLEDGE_DIR, settings.LOGS_DIR]:
        ensure_dir(dir_path)
