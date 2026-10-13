"""Playwright + Pytest UI 自动化框架。"""

from framework.base_page import BasePage
from framework.config import base_url, load_settings

__all__ = ["BasePage", "base_url", "load_settings"]
