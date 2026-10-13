"""失败和跳过时截视口图，挂到 Allure。截图失败只打日志，不掩盖原异常。"""
from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import allure
import pytest
from playwright.sync_api import Page

SKIP_SCREENSHOTS_STASH_KEY = pytest.StashKey()
SKIP_SCREENSHOT_NAMES_STASH_KEY = pytest.StashKey()

SCREENSHOT_TIMEOUT_MS = 5000
_registered_pages: list = []


def resolve_screenshot_dir(case_dir: Path) -> Path:
    env = (os.environ.get("TEST_ENV") or "test").strip().lower()
    return case_dir.resolve() / "screenshots" / env


def register_screenshot_page(page: Page, *, label: str = "") -> None:
    if page is None:
        return
    _registered_pages.append((page, (label or "").strip()))


def clear_registered_screenshot_pages() -> None:
    _registered_pages.clear()


def _page_is_open(page) -> bool:
    if page is None:
        return False
    try:
        return not page.is_closed()
    except Exception:
        return False


def _page_url(page) -> str:
    try:
        url = getattr(page, "url", "") or ""
    except Exception:
        return ""
    return url if isinstance(url, str) else ""


def _safe_label(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (text or ""))
    return (cleaned[:40] or "page")


def screenshot_label(page, *, explicit: str = "") -> str:
    raw = (explicit or "").strip()
    if raw:
        return _safe_label(raw)
    try:
        host = (urlparse(_page_url(page)).hostname or "").split(".")[0]
    except Exception:
        host = ""
    return _safe_label(host or "page")


def _funcarg_pages(funcargs) -> list:
    pages = []
    for _key, value in (funcargs or {}).items():
        if _page_is_open(value):
            pages.append(value)
            continue
        inner = getattr(value, "page", None)
        if _page_is_open(inner):
            pages.append(inner)
    return pages


def _pages_for_screenshot(item, *, all_pages: bool = False) -> list:
    seen = set()
    ordered = []

    def add(page) -> None:
        if not _page_is_open(page):
            return
        ident = id(page)
        if ident in seen:
            return
        seen.add(ident)
        ordered.append(page)

    for page, _label in _registered_pages:
        add(page)

    funcargs = getattr(item, "funcargs", None) or {}
    preferred = funcargs.get("page")
    context = funcargs.get("browser_context")
    if context is None and _page_is_open(preferred):
        context = getattr(preferred, "context", None)
    context_pages = []
    if context is not None:
        try:
            context_pages = [page for page in context.pages if _page_is_open(page)]
        except Exception:
            context_pages = []

    if all_pages:
        add(preferred)
        for page in _funcarg_pages(funcargs):
            add(page)
        for page in context_pages:
            add(page)
        return ordered

    if _page_is_open(preferred):
        add(preferred)
    elif _funcarg_pages(funcargs):
        add(_funcarg_pages(funcargs)[0])
    elif context_pages:
        add(context_pages[-1])
    return ordered


def _label_for_page(page) -> str:
    for registered, explicit in _registered_pages:
        if registered is page and _page_is_open(registered):
            return screenshot_label(page, explicit=explicit)
    return screenshot_label(page)


def _take_page_screenshot(page: Page, path: str) -> bool:
    try:
        page.screenshot(
            path=path,
            full_page=False,
            timeout=SCREENSHOT_TIMEOUT_MS,
            animations="disabled",
        )
        return True
    except Exception as exc:
        print(f"\n[WARN] 截图失败({path}): {exc}")
        return False


def _case_dir(item) -> Path:
    return Path(str(getattr(item, "path", "") or getattr(item, "fspath", ""))).resolve().parent


def _save_screenshots(item, pages, *, tag: str) -> tuple:
    saved = []
    names = {}
    if not pages:
        return saved, names
    target_dir = resolve_screenshot_dir(_case_dir(item))
    target_dir.mkdir(parents=True, exist_ok=True)
    node_id = item.nodeid
    node_hash = hashlib.md5(node_id.encode("utf-8")).hexdigest()[:10]
    node_name = node_id.split("::", 1)[0].replace("/", "_")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    attempt = getattr(item, "execution_count", 1)
    for index, page in enumerate(pages):
        label = _label_for_page(page)
        path = target_dir / (
            f"{node_name}_{tag}_attempt{attempt}_{label}_page{index}_{stamp}_{node_hash}.png"
        )
        if not _take_page_screenshot(page, str(path)):
            continue
        saved.append(str(path))
        url = _page_url(page)
        names[str(path)] = f"{label} {url}".strip() if url else label
        print(f"\n[INFO] {tag} 截图已保存到 {path}")
    return saved, names


def _attach_files(paths, names) -> None:
    for path in paths or []:
        try:
            allure.attach.file(
                path,
                name=(names or {}).get(path, Path(path).stem),
                attachment_type=allure.attachment_type.PNG,
            )
        except Exception as exc:
            print(f"\n[WARN] Allure attach 失败 ({Path(path).name}): {exc}")


def attach_failure_screenshots(item, report) -> None:
    """setup/call 失败时截图。teardown 不截。"""
    if report.when not in ("setup", "call") or not report.failed:
        return
    try:
        pages = _pages_for_screenshot(item, all_pages=True)
        if not pages:
            print("\n[WARN] 未获取到可截图页面，跳过截图")
            return
        paths, names = _save_screenshots(item, pages, tag=report.when)
        _attach_files(paths, names)
    except Exception as exc:
        print(f"\n[ERROR] 截图流程异常: {exc}")


def attach_skip_screenshots(item, report) -> None:
    """跳过时截当前页并挂到 Allure。"""
    if report.when != "call" or not report.skipped:
        return
    try:
        pages = _pages_for_screenshot(item, all_pages=False)
        paths, names = _save_screenshots(item, pages, tag="skip")
        try:
            item.stash[SKIP_SCREENSHOTS_STASH_KEY] = paths
            item.stash[SKIP_SCREENSHOT_NAMES_STASH_KEY] = names
        except Exception:
            pass
        _attach_files(paths, names)
    except Exception as exc:
        print(f"\n[ERROR] 跳过截图流程异常: {exc}")


def capture_and_attach_page_screenshot(
    page: Page, dest_dir: Path, tag: str
) -> Optional[str]:
    """给登录失败等调用方单独截一张图。"""
    try:
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_tag = _safe_label(tag or "page")
        path = dest / f"{safe_tag}_{stamp}.png"
        if not _take_page_screenshot(page, str(path)):
            return None
        url = _page_url(page)
        try:
            allure.attach.file(
                str(path),
                name=f"{tag} {url}".strip() if url else safe_tag,
                attachment_type=allure.attachment_type.PNG,
            )
        except Exception as exc:
            print(f"\n[WARN] Allure attach 失败 ({path.name}): {exc}")
        return str(path)
    except Exception as exc:
        print(f"\n[ERROR] 截图流程异常: {exc}")
        return None
