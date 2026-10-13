"""TodoMVC 示例页。"""
from __future__ import annotations

from playwright.sync_api import expect

from framework.base_page import BasePage


class TodoPage(BasePage):
    def open_app(self) -> None:
        self.open()
        expect(self.page.locator(".new-todo")).to_be_visible()

    def add(self, title: str) -> None:
        field = self.page.locator(".new-todo")
        field.fill(title)
        field.press("Enter")

    def items(self):
        return self.page.locator(".todo-list li")

    def complete(self, title: str) -> None:
        row = self.items().filter(has_text=title)
        row.locator(".toggle").click()
