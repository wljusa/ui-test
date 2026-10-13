"""Pytest 入口：多环境、浏览器夹具、失败截图和耗时。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import allure
import pytest
from playwright.sync_api import Playwright, sync_playwright

from framework.browser import (
    apply_default_timeouts,
    ensure_playwright_browsers_path,
    install_default_timeouts,
    launch_chromium_with_retry,
)
from framework.click_guard import install_click_blocker_guard
from framework.screenshots import attach_failure_screenshots, attach_skip_screenshots
from framework.timing import (
    add_call_seconds,
    add_file_phase,
    format_case_timing,
    format_session_timing,
    iter_file_timing_lines,
    mark_session_start,
    reset_session_timing,
    session_wall_seconds,
    set_current_test_file,
)


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=None,
        choices=["test", "prod"],
        help="选择运行环境: test 或 prod",
    )


def pytest_configure(config):
    ensure_playwright_browsers_path()
    install_default_timeouts()
    install_click_blocker_guard()
    env_from_cli = config.getoption("--env")
    env_name = (os.environ.get("TEST_ENV") or env_from_cli or "test").strip().lower()
    if env_name not in ("test", "prod"):
        raise pytest.UsageError("TEST_ENV/--env 仅支持 test 或 prod")
    os.environ["TEST_ENV"] = env_name


_session_started = 0.0


def pytest_sessionstart(session):
    global _session_started
    reset_session_timing()
    mark_session_start()
    _session_started = time.perf_counter()


def pytest_sessionfinish(session, exitstatus):
    for line in iter_file_timing_lines():
        print("\n" + line)
    wall = session_wall_seconds()
    if _session_started:
        wall = max(wall, time.perf_counter() - _session_started)
    print("\n" + format_session_timing(wall))


def _test_relpath(item) -> Optional[str]:
    raw = getattr(item, "path", None)
    if raw is None:
        return None
    path = Path(raw)
    if not (path.name.startswith("test") and path.suffix == ".py"):
        return None
    root = Path(item.config.rootpath).resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    rel = _test_relpath(item)
    if rel:
        set_current_test_file(rel)
    try:
        yield
    finally:
        if rel:
            set_current_test_file(None)


def _report_duration(item, report) -> None:
    duration = float(getattr(report, "duration", 0) or 0)
    if report.when == "call":
        print("\n" + format_case_timing(item.nodeid, duration))
        add_call_seconds(duration)
    else:
        print(f"\n[耗时] {item.nodeid}  {duration:.2f}s")
    try:
        allure.attach(
            f"{duration:.2f}s",
            name="执行时间",
            attachment_type=allure.attachment_type.TEXT,
        )
    except Exception:
        pass


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    rel = _test_relpath(item)
    if rel and report.when in ("setup", "call", "teardown"):
        add_file_phase(rel, float(getattr(report, "duration", 0) or 0))
    if report.when == "call":
        _report_duration(item, report)
        if report.failed:
            attach_failure_screenshots(item, report)
        if report.skipped:
            attach_skip_screenshots(item, report)
    elif report.when == "setup" and report.failed:
        _report_duration(item, report)
        attach_failure_screenshots(item, report)


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright):
    headed = os.environ.get("HEADED", "").strip().lower() in ("1", "true", "yes")
    launched = launch_chromium_with_retry(playwright_instance, headless=not headed)
    yield launched
    launched.close()


@pytest.fixture
def browser_context(browser):
    kwargs = {"ignore_https_errors": True, "accept_downloads": True}
    state = os.environ.get("STORAGE_STATE", "").strip()
    if state and Path(state).is_file():
        kwargs["storage_state"] = state
    context = browser.new_context(**kwargs)
    apply_default_timeouts(context)
    yield context
    context.close()


@pytest.fixture
def page(browser_context):
    opened = browser_context.new_page()
    yield opened
    if not opened.is_closed():
        opened.close()
