import subprocess
import time
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen
import dotenv
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError
import logging

from logger import setup_logger
from symbol import Symbol

logger = setup_logger('chrome')

dotenv.load_dotenv()

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 18800
DEBUG_URL = f"http://127.0.0.1:{DEBUG_PORT}"
VERSION_URL = f"{DEBUG_URL}/json/version"


def is_cdp_ready() -> bool:
    try:
        with urlopen(VERSION_URL, timeout=1):
            return True
    except URLError:
        return False


def ensure_debug_chrome_running() -> None:
    chrome_path = Path(CHROME_BIN)
    if not chrome_path.exists():
        raise FileNotFoundError(f"未找到本地 Chrome: {chrome_path}")

    # 调试端口可用时直接返回
    if is_cdp_ready():
        logger.info("端口已就绪")
        return

    # 未开启时，后台启动一个可被 Playwright 接管的本地 Chrome 进程
    subprocess.Popen(
        [
            CHROME_BIN,
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-debugging-address=127.0.0.1",
            "--user-data-dir=/Users/li/.openclaw/browser/openclaw/user-data",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # 最多等待 10 秒让 CDP 端口起来
    for _ in range(20):
        if is_cdp_ready():
            return
        time.sleep(0.5)

    raise RuntimeError(
        f"CDP 端口未就绪: {VERSION_URL}。"
        "请先完全退出所有 Chrome 进程后重试，"
        "或手动用 --user-data-dir 启动独立实例。"
    )

def focus_input_box(page: Page):
    page.click('div.json-article-editor')

def input_symbol(page: Page, symbol: Symbol):
    page.keyboard.type(symbol.with_prefix)
    selector = '.tippy-box .tippy-content .bg-cardBg'
    try:
        page.wait_for_selector(selector, timeout=10000)
        time.sleep(3)
        container = page.locator(selector)
        children = container.locator('.text-PrimaryText').all()
        for child in children:
            if child.text_content() == symbol.clean:
                logger.debug(child.text_content())
                child.click()
                break
    except TimeoutError:
        logger.warning(f'{symbol.clean}现货标签没找到')
    finally:
        page.keyboard.type(' ')

def input_text(page: Page, text: str):
    page.keyboard.type(text)

def input_trade_widget(page: Page, symbol: Symbol, is_search: bool = False):
    trade_widget_list_selector = '.bg-CardBg .text-PrimaryText'
    try:
        # 如果需要使用搜索的方式, 超时为0, 快速失败
        timeout = 0 if is_search else 3000
        page.wait_for_selector(trade_widget_list_selector, timeout=timeout)
    except TimeoutError:
        logger.warning(f"wait_for_selector {trade_widget_list_selector} TimeoutError")
    except Exception as e:
        logger.error(e)

    if page.locator(trade_widget_list_selector).count() == 0:
        page.click('.trade-widget-icon.icon-box')
        symbol_name_input_selector = '.bg-CardBg .bn-textField-input'
        page.wait_for_selector(symbol_name_input_selector)
        page.fill(symbol_name_input_selector, symbol.clean)
        time.sleep(1)

    target = symbol.full
    elements = page.locator(trade_widget_list_selector).all()
    for el in elements:
        logger.debug(el.text_content())
        if el.text_content() == target:
            el.click()
            break

def click_post(page: Page):
    buttons = page.locator('.short-editor-inner button').all()
    for button in buttons:
        if "发文" in button.text_content():
            button.click()

def open_page(target_url: str, run: Callable[[Page], None]):
    ensure_debug_chrome_running()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(DEBUG_URL)
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = browser.new_context()

        target_page: Page | None = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if target_url in pg.url:
                    target_page = pg
                    break
            if target_page:
                break

        if target_page:
            page = target_page
            logger.info(f"使用已打开的标签页: {page.url}")
        else:
            page = context.new_page()
            page.goto(target_url, wait_until="domcontentloaded")
            logger.info(f"打开新标签页: {page.url}")

        run(page)

def binance_posting(symbol: Symbol, content: str):
    def run(page: Page):
        focus_input_box(page)
        input_symbol(page, symbol)
        input_text(page, content.removeprefix('\n').removeprefix(symbol.clean))
        input_trade_widget(page, symbol)
        click_post(page)
    target_url = "https://www.bmwweb.academy/zh-CN/square"
    open_page(target_url, run)


def main() -> None:
    ensure_debug_chrome_running()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(DEBUG_URL)
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = browser.new_context()

        TARGET_URL = "https://www.bmwweb.academy/zh-CN/square"

        target_page: Page | None = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if TARGET_URL in pg.url:
                    target_page = pg
                    break
            if target_page:
                break

        if target_page:
            page = target_page
            logger.info(f"使用已打开的标签页: {page.url}")
        else:
            page = context.new_page()
            page.goto(TARGET_URL, wait_until="domcontentloaded")
            logger.info(f"打开新标签页: {page.url}")

        symbol = Symbol.parse('PIPPIN/USDT')
        text = '''各位专家，
        这个拿到什么位置合适出？
        '''

        page.click('div.json-article-editor')
        input_symbol(page, symbol)
        input_text(page, text)
        input_trade_widget(page, symbol)
        # click_post(page)
        # browser.close()


if __name__ == "__main__":
    main()
