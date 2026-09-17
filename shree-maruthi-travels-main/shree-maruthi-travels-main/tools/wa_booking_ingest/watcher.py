"""Read-only WhatsApp Web watcher. Does not send or change messages."""
import asyncio
import base64
import hashlib
from datetime import datetime
from pathlib import Path

import config
import db
from logutil import log

SEARCH_BOXES = [
    'div[contenteditable="true"][data-tab="3"]',
    'div[contenteditable="true"][aria-label*="Search"]',
    'div[contenteditable="true"][data-tab="6"]',
]
CHAT_READY = [
    'div[contenteditable="true"][data-tab="10"]',
    'div[contenteditable="true"][title="Type a message"]',
    '#main',
]


async def _first_locator(page, selectors, timeout=15000):
    last_error = None
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            await loc.wait_for(state='visible', timeout=timeout)
            return loc
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f'WhatsApp UI control not found: {last_error}')


async def _wait_logged_in(page):
    for _ in range(180):
        qr_count = await page.locator('canvas').count()
        side = await page.locator('#pane-side, [data-testid="chat-list"], div[aria-label="Chat list"]').count()
        if qr_count and not side:
            db.set_stat('whatsapp', 'QR')
            log.info('WhatsApp connection status QR — scan once in this window')
        if side:
            db.set_stat('whatsapp', 'CONNECTED')
            log.info('WhatsApp connection status CONNECTED')
            return
        await page.wait_for_timeout(2000)
    raise RuntimeError('WhatsApp Web did not become ready')


async def _open_group(page, name):
    box = await _first_locator(page, SEARCH_BOXES, timeout=20000)
    await box.click()
    await page.keyboard.press('Control+A')
    await page.keyboard.press('Backspace')
    await box.type(name, delay=40)
    await page.wait_for_timeout(1200)
    result = page.locator(f'span[title="{name}"]').first
    if await result.count() == 0:
        result = page.get_by_title(name, exact=False).first
    await result.click(timeout=15000)
    await page.wait_for_timeout(1500)
    db.set_stat('target_group', 'FOUND')
    log.info('target group detection FOUND %s', name)


async def _collect_images(page):
    return await page.evaluate(
        """() => {
          const nodes = [...document.querySelectorAll('div[data-id]')].slice(-50);
          const out = [];
          for (const node of nodes) {
            const img = node.querySelector('img[src^="blob:"], img[src*="mmg.whatsapp"]');
            if (!img || !img.src) continue;
            out.push({ id: node.getAttribute('data-id') || '', src: img.src });
          }
          return out;
        }"""
    )


async def _download_image(page, src, message_id):
    data = await page.evaluate(
        """async (url) => {
          const res = await fetch(url);
          const buf = await res.arrayBuffer();
          const bytes = new Uint8Array(buf);
          let binary = '';
          for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
          return btoa(binary);
        }""",
        src,
    )
    raw = base64.b64decode(data)
    digest = hashlib.sha1((message_id + src[:40]).encode('utf-8')).hexdigest()[:12]
    stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    path = config.INCOMING_DIR / f'{stamp}-{digest}.jpg'
    path.write_bytes(raw)
    return path


async def watch_forever():
    from playwright.async_api import async_playwright

    config.ensure_dirs()
    if not config.TARGET_WHATSAPP_GROUP:
        raise RuntimeError('Set TARGET_WHATSAPP_GROUP in .env')
    log.info('starting WhatsApp watcher group=%s', config.TARGET_WHATSAPP_GROUP)
    while True:
        try:
            async with async_playwright() as pw:
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(config.PROFILE_DIR),
                    headless=config.HEADLESS,
                    args=['--disable-dev-shm-usage'],
                    viewport={'width': 1280, 'height': 900},
                )
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto('https://web.whatsapp.com/', wait_until='domcontentloaded')
                await _wait_logged_in(page)
                await _open_group(page, config.TARGET_WHATSAPP_GROUP)
                if config.SKIP_EXISTING_ON_START:
                    existing = await _collect_images(page)
                    for item in existing:
                        mid = item.get('id') or hashlib.sha1(item.get('src', '').encode()).hexdigest()
                        if not db.message_seen(mid):
                            db.mark_message(mid, config.TARGET_WHATSAPP_GROUP, '', 'skipped_startup', 'already on screen at start')
                    log.info('skipped %s existing images on start', len(existing))
                while True:
                    try:
                        if page.is_closed():
                            raise RuntimeError('WhatsApp tab closed')
                        items = await _collect_images(page)
                        for item in items:
                            mid = item.get('id') or hashlib.sha1((item.get('src') or '').encode()).hexdigest()
                            if not mid or db.message_seen(mid):
                                continue
                            log.info('new image detected %s', mid)
                            db.set_stat('last_image', datetime.utcnow().isoformat(timespec='seconds') + 'Z')
                            path = await _download_image(page, item['src'], mid)
                            log.info('image downloaded %s', path.name)
                            db.mark_message(mid, config.TARGET_WHATSAPP_GROUP, str(path), 'queued', '')
                            db.enqueue_job('ocr_image', {
                                'image_path': str(path),
                                'message_id': mid,
                                'group_name': config.TARGET_WHATSAPP_GROUP,
                            })
                        db.set_stat('whatsapp', 'CONNECTED')
                    except Exception as exc:
                        log.error('watch loop error %s', exc)
                        db.set_stat('last_error', str(exc)[:300])
                        db.set_stat('whatsapp', 'DISCONNECTED')
                        raise
                    await page.wait_for_timeout(config.POLL_SECONDS * 1000)
        except Exception as exc:
            log.error('browser/session error %s — retrying', exc)
            db.set_stat('whatsapp', 'DISCONNECTED')
            db.set_stat('last_error', str(exc)[:300])
            await asyncio.sleep(8)
