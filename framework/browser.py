"""浏览器启动、默认超时，以及忽略一次性沙箱里的浏览器缓存路径。"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Optional

from playwright.sync_api import Browser, Playwright

ACTION_TIMEOUT_MS = 15_000
NAVIGATION_TIMEOUT_MS = 30_000

_installed = False
_SANDBOX_MARKERS = ("cursor-sandbox-cache",)


def ensure_playwright_browsers_path() -> None:
    """沙箱把浏览器装到临时目录时，改回本机缓存，避免每次都报未安装。"""
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if not browsers_path:
        return
    if any(marker in browsers_path for marker in _SANDBOX_MARKERS):
        os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)


def apply_default_timeouts(context: Any) -> Any:
    """动作 15 秒；导航单独 30 秒。调用处已写的 timeout 不变。"""
    context.set_default_timeout(ACTION_TIMEOUT_MS)
    context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    return context


def _wrap_new_context(orig: Callable) -> Callable:
    def wrapped(self, *args, **kwargs):
        return apply_default_timeouts(orig(self, *args, **kwargs))

    return wrapped


def _wrap_new_page(orig: Callable) -> Callable:
    def wrapped(self, *args, **kwargs):
        page = orig(self, *args, **kwargs)
        apply_default_timeouts(page.context)
        return page

    return wrapped


def install_default_timeouts() -> None:
    """包一层 Browser.new_context / new_page。重复调用直接返回。"""
    global _installed
    if _installed:
        return
    from playwright.sync_api import Browser as BrowserType

    BrowserType.new_context = _wrap_new_context(BrowserType.new_context)
    BrowserType.new_page = _wrap_new_page(BrowserType.new_page)
    _installed = True


def launch_chromium_with_retry(
    playwright: Playwright,
    *,
    headless: bool = True,
    slow_mo: int = 0,
    attempts: int = 3,
    retry_delay_sec: float = 0.8,
    **launch_kwargs: Any,
) -> Browser:
    """Chromium 偶发启动即退出时重试，避免整场被一次崩溃打掉。"""
    last_error: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        try:
            return playwright.chromium.launch(
                headless=headless,
                slow_mo=slow_mo,
                **launch_kwargs,
            )
        except Exception as exc:
            last_error = exc
            print(
                f"\n[WARN] Chromium launch 失败 ({attempt}/{attempts}): "
                f"{type(exc).__name__}: {exc}"
            )
            if attempt < attempts:
                time.sleep(retry_delay_sec * attempt)
    assert last_error is not None
    raise last_error
