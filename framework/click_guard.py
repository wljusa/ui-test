"""Locator.click 被全屏 loading 挡住时，先短等再摘掉遮罩，避免空等默认超时。

调用方已传 timeout 或 force=True 时原样执行。没有遮罩时仍走默认超时。
遮罩选择器可配置，默认兼容 Element Plus 的 .el-loading-mask，以及示例页的 .ui-loading-mask。
"""
from __future__ import annotations

from typing import Callable, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect

CLICK_RETRY_MS = 3000
MASK_GRACE_MS = 2000
DEFAULT_MASK_SELECTOR = (
    ".el-loading-mask.is-fullscreen, .ui-loading-mask.is-fullscreen"
)

_mask_selector = DEFAULT_MASK_SELECTOR
_orig_click: Optional[Callable] = None
_installed = False
_in_retry = False

_MASK_ON_JS = """(el, selector) => {
    const mask = document.querySelector(selector);
    if (!mask) return false;
    const style = window.getComputedStyle(mask);
    const box = mask.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden'
        && box.width > 0 && box.height > 0;
}"""
_REMOVE_MASK_JS = """(selector) => {
    document.querySelectorAll(selector).forEach((node) => node.remove());
}"""


def configure_click_guard(mask_selector: str = DEFAULT_MASK_SELECTOR) -> None:
    """安装前或运行中更换遮罩选择器。选择器必须是 querySelector 能识别的 CSS。"""
    global _mask_selector
    selector = (mask_selector or "").strip()
    if not selector:
        raise ValueError("mask_selector 不能为空")
    _mask_selector = selector


def release_stuck_fullscreen_loading(page, grace_ms: int = MASK_GRACE_MS) -> None:
    """全屏 loading 挡住点击时先短等；仍不消失就摘掉。"""
    selector = _mask_selector
    try:
        mask = page.locator(selector)
        if mask.count() == 0:
            return
    except Exception:
        return
    if grace_ms > 0:
        try:
            expect(mask).to_have_count(0, timeout=grace_ms)
            return
        except Exception:
            pass
    try:
        if mask.count() == 0:
            return
        page.evaluate(_REMOVE_MASK_JS, selector)
    except Exception:
        return


def _mask_on(locator) -> bool:
    try:
        return bool(locator.evaluate(_MASK_ON_JS, _mask_selector))
    except Exception:
        pass
    try:
        return locator.page.locator(_mask_selector).count() > 0
    except Exception:
        return False


def _invoke_click(locator, *args, **kwargs):
    if _orig_click is not None:
        return _orig_click(locator, *args, **kwargs)
    return locator.click(*args, **kwargs)


def click_with_blocker_retry(locator, *args, **kwargs):
    """清掉遮罩后点击。单次最多 3 秒，超时再清一次并重试一次。"""
    global _in_retry
    timeout = kwargs.pop("timeout", CLICK_RETRY_MS)
    if _in_retry:
        return _invoke_click(locator, *args, timeout=timeout, **kwargs)
    _in_retry = True
    try:
        release_stuck_fullscreen_loading(locator.page, grace_ms=MASK_GRACE_MS)
        try:
            return _invoke_click(locator, *args, timeout=timeout, **kwargs)
        except PlaywrightTimeoutError:
            release_stuck_fullscreen_loading(locator.page, grace_ms=0)
            return _invoke_click(locator, *args, timeout=timeout, **kwargs)
    finally:
        _in_retry = False


def _guarded_click(orig: Callable) -> Callable:
    def _wrapped(self, *args, **kwargs):
        if _in_retry or kwargs.get("force") or "timeout" in kwargs:
            return orig(self, *args, **kwargs)
        if not _mask_on(self):
            return orig(self, *args, **kwargs)
        return click_with_blocker_retry(self, *args, **kwargs)

    return _wrapped


def install_click_blocker_guard(
    mask_selector: str = DEFAULT_MASK_SELECTOR,
) -> None:
    """包一层 Locator.click。重复调用只更新选择器。"""
    global _orig_click, _installed
    configure_click_guard(mask_selector)
    if _installed:
        return
    from playwright.sync_api import Locator

    _orig_click = Locator.click
    Locator.click = _guarded_click(_orig_click)
    _installed = True
