"""按 --env / TEST_ENV 读取配置。地址和账号只来自 yaml 或环境变量。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = ("test", "prod")


def resolve_env_name(explicit: Optional[str] = None) -> str:
    """优先显式参数，其次 TEST_ENV，默认 test。"""
    name = (explicit or os.environ.get("TEST_ENV") or "test").strip().lower()
    if name not in ENVIRONMENTS:
        raise ValueError("TEST_ENV/--env 仅支持 test 或 prod")
    return name


def settings_path() -> Path:
    """本地 settings.yaml 优先；没有则用仓库里的示例。"""
    local = ROOT / "config" / "settings.yaml"
    if local.is_file():
        return local
    return ROOT / "config" / "settings.example.yaml"


def load_settings(
    env: Optional[str] = None, path: Optional[Path] = None
) -> Dict[str, Any]:
    """返回当前环境配置。BASE_URL 环境变量覆盖 yaml 里的 base_url。"""
    env_name = resolve_env_name(env)
    source = Path(path) if path is not None else settings_path()
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    block = dict(raw.get(env_name) or {})
    override = os.environ.get("BASE_URL", "").strip()
    if override:
        block["base_url"] = override
    block.setdefault("base_url", "")
    return block


def base_url(env: Optional[str] = None) -> str:
    return str(load_settings(env).get("base_url") or "").rstrip("/")
