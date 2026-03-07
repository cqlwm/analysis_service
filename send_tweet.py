import argparse

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError
from playwright.sync_api import sync_playwright

from attach_existing_chrome import DEBUG_URL
from attach_existing_chrome import ensure_debug_chrome_running
from logger import setup_logger

logger = setup_logger("send_tweet")

EDITOR_SELECTOR = ".DraftEditor-root .DraftEditor-editorContainer"
HOME_TWEET_BUTTON_SELECTOR = '[data-testid="tweetButtonInline"]'
COMPOSE_TWEET_BUTTON_SELECTOR = '[data-testid="tweetButton"]'


def open_x_page(page: Page) -> bool:
    page.goto("https://x.com", wait_until="domcontentloaded")
    try:
        page.wait_for_selector(EDITOR_SELECTOR, timeout=10000)
        return False
    except TimeoutError:
        page.goto("https://x.com/compose/post", wait_until="domcontentloaded")
        page.wait_for_selector(EDITOR_SELECTOR, timeout=20000)
        return True


def input_tweet_content(page: Page, content: str) -> None:
    editor = page.locator(EDITOR_SELECTOR).first
    editor.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    page.keyboard.type(content, delay=20)
    logger.info("推文内容: %s", content)


def submit_tweet(page: Page, opened_from_compose_post: bool) -> None:
    tweet_button_selector = (
        COMPOSE_TWEET_BUTTON_SELECTOR
        if opened_from_compose_post
        else HOME_TWEET_BUTTON_SELECTOR
    )
    page.wait_for_selector(tweet_button_selector, timeout=10000)
    tweet_button = page.locator(tweet_button_selector).first
    tweet_button.click()
    logger.info("推文已发送")


def send_tweet(content: str, dry_run: bool) -> None:
    ensure_debug_chrome_running()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(DEBUG_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        opened_from_compose_post = open_x_page(page)
        input_tweet_content(page, content)

        if dry_run:
            logger.info("dry-run 模式，已跳过发送按钮点击")
            return

        submit_tweet(page, opened_from_compose_post)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="自动填写并发送推特")
    parser.add_argument("content", help="要发送的推文内容")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只填写并输出推文内容，不点击发送",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    send_tweet(args.content, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
