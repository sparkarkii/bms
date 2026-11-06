import json
from pathlib import Path
from playwright.sync_api import (
    sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeout,
)

FAILED = Path('test.json')
PROFILE = Path('pw-profile')          # keeps logins and cookies between runs


def grab_direct_url(page, url: str) -> dict | None:
    try:
        with page.expect_download(timeout=300_000) as info:   # 5 min for you to click
            try:
                page.goto(url)
            except PlaywrightError:
                pass      # if the URL itself is a download, navigation aborts
        download = info.value
    except PlaywrightTimeout:
        return None
    result = {'direct_url': download.url, 'filename': download.suggested_filename}
    download.cancel()
    return result


def main():
    items = json.loads(FAILED.read_text(encoding='utf-8'))
    with sync_playwright() as p:
        context = p.firefox.launch_persistent_context(PROFILE, headless=False)
        page = context.new_page()
        for item in items:
            if item.get('direct_url'):
                continue                      # done already, so reruns resume
            if (found := grab_direct_url(page, item['url'])):
                item.update(found)
            FAILED.write_text(
                json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8'
            )                                 # save after every item
        context.close()


if __name__ == '__main__':
    main()
