"""环境配置只从 yaml 和环境变量来。"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.config import base_url, load_settings, resolve_env_name


SAMPLE = """
test:
  base_url: https://example.test
prod:
  base_url: https://example.prod
"""


def test_resolve_env_rejects_unknown(monkeypatch):
    monkeypatch.delenv("TEST_ENV", raising=False)
    assert resolve_env_name(None) == "test"
    with pytest.raises(ValueError):
        resolve_env_name("staging")


def test_load_settings_by_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("BASE_URL", raising=False)
    path = tmp_path / "settings.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    assert load_settings("test", path)["base_url"] == "https://example.test"
    assert load_settings("prod", path)["base_url"] == "https://example.prod"


def test_base_url_env_overrides_yaml(tmp_path: Path, monkeypatch):
    path = tmp_path / "settings.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("BASE_URL", "https://override.example")
    assert load_settings("prod", path)["base_url"] == "https://override.example"
    monkeypatch.setenv("TEST_ENV", "test")
    # base_url() 读仓库配置；这里只验证覆盖函数本身走环境变量。
    monkeypatch.setattr("framework.config.settings_path", lambda: path)
    assert base_url() == "https://override.example"
