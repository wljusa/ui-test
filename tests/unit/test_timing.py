"""会话登录耗时与用例耗时。"""
from __future__ import annotations

import time

from framework.timing import (
    add_call_seconds,
    add_file_phase,
    add_login_seconds,
    call_seconds,
    file_exec_seconds,
    format_case_timing,
    format_file_timing_line,
    format_session_timing,
    login_seconds,
    mark_session_start,
    measure_login,
    reset_session_timing,
    session_wall_seconds,
    set_current_test_file,
)


def setup_function() -> None:
    reset_session_timing()


def test_add_login_and_call_seconds():
    add_login_seconds(12.5)
    add_call_seconds(3.25)
    add_call_seconds(1.0)
    assert abs(login_seconds() - 12.5) < 1e-6
    assert abs(call_seconds() - 4.25) < 1e-6


def test_negative_seconds_are_ignored():
    add_login_seconds(-3)
    add_call_seconds(-1)
    assert login_seconds() == 0.0
    assert call_seconds() == 0.0


def test_format_session_timing():
    add_login_seconds(12.5)
    add_call_seconds(4.25)
    line = format_session_timing(20.0)
    assert line == "[会话耗时] 登录 12.50s | 用例 4.25s | 墙钟 20.00s"


def test_measure_login_context_adds_elapsed():
    with measure_login():
        time.sleep(0.02)
    assert login_seconds() >= 0.02
    assert call_seconds() == 0.0


def test_session_wall_seconds_after_mark():
    mark_session_start()
    time.sleep(0.02)
    assert session_wall_seconds() >= 0.02


def test_login_deducted_only_from_owning_file():
    owning = "examples/tests/test_a.py"
    other = "examples/tests/test_b.py"
    set_current_test_file(owning)
    add_file_phase(owning, 30)
    add_file_phase(other, 10)
    add_login_seconds(5)
    assert abs(file_exec_seconds(owning) - 25) < 1e-6
    assert abs(file_exec_seconds(other) - 10) < 1e-6
    assert "已扣登录 5.00s" in format_file_timing_line(owning)


def test_slow_case_is_marked_not_failed_by_formatter():
    line = format_case_timing("examples/tests/test_todo.py::test_add", 21.2)
    assert "超限" in line
    assert "21.20s" in line
