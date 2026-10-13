"""页面对象基类：打开页面、点击、填写、弹窗和表头。"""
from __future__ import annotations

import re
from typing import Iterable, Optional, Union

from playwright.sync_api import Page, expect

from framework.click_guard import release_stuck_fullscreen_loading

TitlePattern = Union[str, re.Pattern]


class BasePage:
    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = (base_url or "").rstrip("/")

    def reopen_if_closed(self) -> None:
        if not self.page.is_closed():
            return
        self.page = self.page.context.new_page()

    def open(self, path: str = "") -> None:
        """path 为空时打开 base_url；以 http 开头时当作完整地址。"""
        self.reopen_if_closed()
        target = (path or "").strip()
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        elif not target:
            url = self.base_url
        else:
            url = f"{self.base_url}/{target.lstrip('/')}"
        if not url:
            raise ValueError("base_url 为空，无法打开页面")
        self.page.goto(url, wait_until="domcontentloaded")
        self.wait_loading_settled()

    def click_button(self, name: str, *, exact: bool = False) -> None:
        self.page.get_by_role("button", name=name, exact=exact).first.click()

    def click_text(self, text: str, *, exact: bool = False) -> None:
        self.page.get_by_text(text, exact=exact).first.click()

    def fill_labeled_input(self, label: str, value: str) -> None:
        field = self.page.get_by_label(label, exact=False)
        if field.count() == 0:
            field = self.page.locator(
                f"xpath=//*[contains(normalize-space(.),'{label}')]/following::input[1]"
            )
        field.first.fill(value)

    def select_combobox_option(self, label: str, option_text: str) -> None:
        box = self.page.get_by_role("combobox", name=label)
        if box.count() == 0:
            box = self.page.get_by_label(label, exact=False)
        box.first.click()
        self.page.get_by_role("option", name=option_text, exact=True).click()

    def dialog_scope(self):
        return self.page.locator('[role="dialog"]:visible, .el-dialog:visible').first

    def wait_dialog(self, title_pattern: Optional[TitlePattern] = None) -> None:
        dialog = self.dialog_scope()
        expect(dialog).to_be_visible()
        if title_pattern:
            expect(dialog.filter(has_text=title_pattern)).to_be_visible()

    def table_header_texts(self) -> list:
        headers = self.page.get_by_role("columnheader")
        if headers.count() > 0:
            return [
                headers.nth(index).inner_text().strip()
                for index in range(headers.count())
            ]
        cells = self.page.locator("thead th:visible, .el-table__header th:visible")
        return [cells.nth(index).inner_text().strip() for index in range(cells.count())]

    def expect_table_headers_contain(self, names: Iterable[str]) -> None:
        joined = " ".join(self.table_header_texts())
        missing = [name for name in names if name not in joined]
        if missing:
            raise AssertionError(f"表头缺少 {missing}，当前表头: {joined}")

    def wait_loading_settled(self, timeout_ms: int = 15000) -> None:
        """等全屏 loading 消失。页面上没有遮罩时立即返回。"""
        loading = self.page.locator(
            ".el-loading-mask:visible, .ui-loading-mask:visible"
        )
        if loading.count() == 0:
            return
        try:
            expect(loading).to_have_count(0, timeout=timeout_ms)
        except Exception:
            release_stuck_fullscreen_loading(self.page, grace_ms=0)
