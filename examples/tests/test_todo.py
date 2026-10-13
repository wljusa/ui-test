import re

from playwright.sync_api import expect

from examples.pages.todo_page import TodoPage
from framework.config import base_url


def test_add_and_complete_todo(page):
    todo = TodoPage(page, base_url())
    todo.open_app()
    todo.add("买牛奶")
    expect(todo.items()).to_have_count(1)
    todo.complete("买牛奶")
    expect(todo.items().first).to_have_class(re.compile(r"completed"))
