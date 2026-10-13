"""把一次 pytest 会话拆成登录耗时和用例 call 耗时。

单条用例 call 超过 20 秒只在日志里标「超限」，不因此判失败。
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict, Iterator, Optional

CASE_EXEC_LIMIT_SECONDS = 20.0

_login_seconds = 0.0
_call_seconds = 0.0
_session_start = 0.0
_current_test_file: Optional[str] = None
_file_phase_seconds: Dict[str, float] = {}
_file_login_seconds: Dict[str, float] = {}


def reset_session_timing() -> None:
    global _login_seconds, _call_seconds, _session_start, _current_test_file
    _login_seconds = 0.0
    _call_seconds = 0.0
    _session_start = 0.0
    _current_test_file = None
    _file_phase_seconds.clear()
    _file_login_seconds.clear()


def mark_session_start() -> None:
    global _session_start
    _session_start = time.perf_counter()


def set_current_test_file(path: Optional[str]) -> None:
    global _current_test_file
    _current_test_file = None if path is None else str(path)


def add_login_seconds(seconds: float) -> None:
    """累加会话登录，并在有当前测试文件时记入该文件的可扣除登录。"""
    global _login_seconds
    elapsed = max(0.0, float(seconds))
    _login_seconds += elapsed
    if _current_test_file is None or elapsed <= 0:
        return
    key = _current_test_file
    _file_login_seconds[key] = _file_login_seconds.get(key, 0.0) + elapsed


def add_call_seconds(seconds: float) -> None:
    global _call_seconds
    _call_seconds += max(0.0, float(seconds))


def add_file_phase(path: str, seconds: float) -> None:
    elapsed = float(seconds)
    if elapsed < 0:
        return
    key = str(path)
    _file_phase_seconds[key] = _file_phase_seconds.get(key, 0.0) + elapsed


def login_seconds() -> float:
    return _login_seconds


def call_seconds() -> float:
    return _call_seconds


def file_login_seconds(path: str) -> float:
    return _file_login_seconds.get(str(path), 0.0)


def file_exec_seconds(path: str) -> float:
    key = str(path)
    net = _file_phase_seconds.get(key, 0.0) - _file_login_seconds.get(key, 0.0)
    return max(0.0, net)


def session_wall_seconds() -> float:
    if _session_start <= 0:
        return 0.0
    return max(0.0, time.perf_counter() - _session_start)


@contextmanager
def measure_login() -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        add_login_seconds(time.perf_counter() - started)


def format_session_timing(wall_sec: float) -> str:
    return (
        f"[会话耗时] 登录 {login_seconds():.2f}s | "
        f"用例 {call_seconds():.2f}s | "
        f"墙钟 {float(wall_sec):.2f}s"
    )


def format_case_timing(
    nodeid: str, seconds: float, limit: float = CASE_EXEC_LIMIT_SECONDS
) -> str:
    over = " | 超限" if float(seconds) > limit else ""
    return f"[耗时] {nodeid}  {float(seconds):.2f}s{over}"


def format_file_timing_line(path: str) -> str:
    return (
        f"[文件耗时] {path}  执行 {file_exec_seconds(path):.2f}s | "
        f"已扣登录 {file_login_seconds(path):.2f}s"
    )


def iter_file_timing_lines() -> Iterator[str]:
    for path in sorted(_file_phase_seconds):
        yield format_file_timing_line(path)
