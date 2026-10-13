Playwright + Pytest UI automation framework: page objects, multi-env config, failure screenshots, and loading-mask click recovery.

# ui-test

从多端 UI 自动化项目里抽出的 Playwright + Pytest 框架。仓库只保留可复用的运行能力，并附一个不需要账号的示例，克隆后即可运行。

## 能做什么

- 用 `--env=test|prod` 切换环境，`base_url` 来自配置文件，可用 `BASE_URL` 覆盖
- Page Object 基类：打开页面、按按钮或文案点击、按标签填写、等待弹窗、读取表头
- 浏览器默认动作超时 15 秒、导航超时 30 秒；Chromium 启动失败会重试
- 全屏 loading 挡住点击时先短等，仍不消失就摘掉遮罩再点，避免空等到超时
- 用例失败或跳过时截视口图，挂到 Allure
- 会话结束打印登录耗时、用例耗时和墙钟时间；单条用例超过 20 秒只打标记

## 目录

```
framework/          配置、浏览器、页面基类、点击守卫、截图、耗时
conftest.py         pytest 夹具与钩子
config/             settings.example.yaml
examples/           TodoMVC 示例，以及本地 loading 遮罩示例
tests/unit/         不打开浏览器的单元测试
```

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 运行

```bash
pytest --env=test
pytest tests/unit
pytest examples/tests --env=test
```

本地想看浏览器时加 `HEADED=1`。已有登录态时把 Playwright `storage_state` 的路径赋给 `STORAGE_STATE`，上下文会自动带上。

## 持续集成

工作流在 [`ci/ui.yml`](ci/ui.yml)。复制到 `.github/workflows/ui.yml` 后，推送到 GitHub 会安装 Chromium 并执行单元测试和示例。当前账号的命令行令牌没有 `workflow` 权限时，GitHub 会拒绝直接提交 `.github/workflows` 下的文件。

## 换成自己的项目

1. 复制 `config/settings.example.yaml` 为 `config/settings.yaml`（该文件已在 `.gitignore` 中）。
2. 为 `test` 和 `prod` 分别填写 `base_url`。账号、密码、token 用环境变量传入，不要写进仓库。
3. 让页面类继承 `framework.base_page.BasePage`，在 `examples/tests` 旁新增自己的用例，夹具名仍是 `page`。

```python
from framework.base_page import BasePage
from framework.config import base_url

class LoginPage(BasePage):
    def open_login(self) -> None:
        self.open("/login")

def test_open_login(page):
    LoginPage(page, base_url()).open_login()
```
