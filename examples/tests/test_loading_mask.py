from pathlib import Path

from playwright.sync_api import expect


def test_click_through_fullscreen_loading(page):
    html = Path(__file__).resolve().parents[1] / "fixtures" / "loading_mask.html"
    page.goto(html.as_uri())
    page.locator("#go").click()
    expect(page.locator("body")).to_have_attribute("data-clicked", "1")
    expect(page.locator("#mask")).to_have_count(0)
