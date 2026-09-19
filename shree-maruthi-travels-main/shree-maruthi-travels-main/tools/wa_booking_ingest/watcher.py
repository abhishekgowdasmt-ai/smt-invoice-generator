"""Read-only WhatsApp Web watcher. Does not send or change messages."""
import asyncio
import base64
import hashlib
import re
from datetime import datetime

import config
import db
from logutil import log

LIST_CHATS_JS = r"""() => {
  const titles = [];
  const seen = new Set();
  const add = (value) => {
    const title = String(value || '').trim();
    if (!title || seen.has(title)) return;
    seen.add(title);
    titles.push(title);
  };
  const timePattern = /^(?:\d{1,2}:\d{2}(?:\s?[ap]m)?|today|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)$/i;
  const pane = document.querySelector('#pane-side, #side, [aria-label="Chat list"], [data-testid="chat-list"]');
  const rows = [...document.querySelectorAll('[role="listitem"], [role="row"], [data-testid="cell-frame-container"]')];
  for (const row of rows) {
    const titled = [...row.querySelectorAll('[title]')]
      .map((node) => (node.getAttribute('title') || '').trim())
      .filter((text) => text && !timePattern.test(text));
    if (titled[0]) { add(titled[0]); continue; }
    const frame = row.querySelector('[data-testid="cell-frame-title"]');
    if (frame && frame.textContent) { add(frame.textContent); continue; }
    const lines = (row.innerText || '').split(/\n+/).map((line) => line.trim()).filter(Boolean);
    const line = lines.find((text) => text && !timePattern.test(text));
    if (line) add(line);
  }
  document.querySelectorAll('#pane-side span[title], #side span[title], [data-testid="cell-frame-title"]').forEach((node) => {
    add(node.getAttribute('title') || node.textContent);
  });
  if (!titles.length && pane) {
    (pane.innerText || '').split(/\n+/).forEach((line) => {
      const text = line.trim();
      if (text && text.length > 2 && !timePattern.test(text)) add(text);
    });
  }
  return titles;
}"""

DIAG_JS = r"""() => {
  const body = (document.body && document.body.innerText) || '';
  const pane = document.querySelector('#pane-side, #side, [aria-label="Chat list"], [data-testid="chat-list"]');
  const qrNode = document.querySelector(
    'canvas[aria-label*="Scan" i], canvas[aria-label*="QR" i], div[data-testid="qrcode"], div[data-ref], canvas[aria-label*="scan" i]'
  );
  const qrCanvas = document.querySelector('div[data-ref] canvas, [data-testid="qrcode"] canvas');
  const dbError = /database error occurred|relink your device|please relink/i.test(body);
  const qrLogin = /scan the qr|scan to log in/i.test(body);
  const listitems = document.querySelectorAll('[role="listitem"]').length;
  const rows = document.querySelectorAll('[role="row"]').length;
  const search = !!document.querySelector('div[contenteditable="true"][data-tab="3"], div[contenteditable="true"][aria-label*="Search" i], #side div[contenteditable="true"]');
  const chatUi = !!(pane || listitems || rows || search);
  return {
    url: location.href,
    title: document.title,
    pane: !!pane,
    qr: ((!!(qrNode || qrCanvas) || qrLogin) && !chatUi && !dbError),
    qrLogin,
    dbError,
    listitems,
    rows,
    titled: document.querySelectorAll('span[title]').length,
    main: !!document.querySelector('#main'),
    search,
    chatUi,
    authenticated: chatUi && !dbError && !/relink your device/i.test(body),
    webdriver: !!navigator.webdriver,
    serviceWorker: !!navigator.serviceWorker,
    paneText: pane ? (pane.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 40) : [],
    bodySample: body.split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 12),
  };
}"""

INDEXEDDB_PROBE_JS = r"""async () => {
  const out = { indexedDB: typeof indexedDB !== 'undefined', open: false, error: '', databases: 0 };
  try {
    if (!indexedDB) {
      out.error = 'indexedDB missing';
      return out;
    }
    if (indexedDB.databases) {
      const dbs = await indexedDB.databases();
      out.databases = (dbs || []).length;
    }
    await new Promise((resolve, reject) => {
      const req = indexedDB.open('wa_ingest_probe', 1);
      req.onerror = () => reject(req.error || new Error('open failed'));
      req.onsuccess = () => {
        try { req.result.close(); } catch (e) {}
        try { indexedDB.deleteDatabase('wa_ingest_probe'); } catch (e) {}
        resolve();
      };
    });
    out.open = true;
  } catch (err) {
    out.error = String(err && err.message ? err.message : err);
  }
  return out;
}"""

CLICK_CHAT_JS = r"""(name) => {
  const wanted = String(name || '').trim().toLowerCase();
  const compact = (value) => String(value || '').toLowerCase().replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim();
  const nodes = [...document.querySelectorAll(
    '#pane-side span[title], #side span[title], [role="listitem"] span[title], [role="row"] span[title], [data-testid="cell-frame-title"] span[title]'
  )];
  const match = nodes.find((node) => (node.getAttribute('title') || '').trim().toLowerCase() === wanted)
    || nodes.find((node) => compact(node.getAttribute('title')).includes(compact(wanted)))
    || nodes.find((node) => compact(wanted).includes(compact(node.getAttribute('title'))));
  if (!match) return { ok: false, title: '' };
  const clickable = match.closest('[role="listitem"]') || match.closest('[role="row"]') || match.closest('div[tabindex]') || match;
  clickable.click();
  return { ok: true, title: (match.getAttribute('title') || '').trim() };
}"""

HEADER_JS = r"""() => {
  const header = document.querySelector('#main header');
  if (!header) return '';
  const titled = header.querySelector('span[title]');
  if (titled && titled.getAttribute('title')) return titled.getAttribute('title').trim();
  return (header.innerText || '').split('\n')[0].trim();
}"""

COLLECT_IMAGES_JS = r"""() => {
  const main = document.querySelector('#main');
  if (!main) return [];
  const out = [];
  const nodes = [...main.querySelectorAll('[data-id], [data-testid="msg-container"]')];
  for (const node of nodes.slice(-80)) {
    const id = node.getAttribute('data-id') || node.getAttribute('data-testid') || '';
    const imgs = [...node.querySelectorAll('img')];
    for (const img of imgs) {
      const src = img.getAttribute('src') || '';
      if (!src) continue;
      if (!(src.startsWith('blob:') || src.includes('whatsapp.net') || src.includes('mmg.whatsapp'))) continue;
      const width = img.naturalWidth || img.width || 0;
      if (width && width < 90) continue;
      if (img.closest('header')) continue;
      out.push({ id: id || src.slice(-24), src, width });
    }
  }
  return out;
}"""

DOWNLOAD_JS = r"""async (url) => {
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}"""


def _norm(value):
    text = re.sub(r'[-_]+', ' ', str(value or '').lower())
    return re.sub(r'\s+', ' ', text).strip()


def _names_match(visible, wanted):
    left, right = _norm(visible), _norm(wanted)
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) < 12:
        return False
    return longer.startswith(shorter) or longer.startswith(shorter + ' ')


def _header_is_target(visible, wanted):
    """Opened-chat check: normalized names must be equal, not a short substring."""
    left, right = _norm(visible), _norm(wanted)
    return bool(left) and left == right


async def _chat_names(page):
    try:
        names = await page.evaluate(LIST_CHATS_JS)
        return [str(name).strip() for name in names if str(name).strip()]
    except Exception as exc:
        log.warning('[WhatsApp] Could not read chat list: %s', exc)
        return []


async def _header_title(page):
    try:
        return str(await page.evaluate(HEADER_JS) or '').strip()
    except Exception:
        return ''


async def _diag(page):
    try:
        return await page.evaluate(DIAG_JS) or {}
    except Exception as exc:
        return {'error': str(exc), 'url': page.url}


async def _dismiss_popups(page):
    labels = ('Continue', 'OK', 'Use here', 'Next', 'Got it', 'Not now')
    for label in labels:
        loc = page.get_by_role('button', name=label)
        try:
            if await loc.count() == 0:
                continue
            await loc.first.click(timeout=1500)
            log.info('[WhatsApp] Dismissed dialog: %s', label)
            await page.wait_for_timeout(800)
        except Exception:
            continue


async def _wait_logged_in(page, console_notes):
    from session import DiagnosticStop, page_reports_db_error

    log.info('[WhatsApp] Waiting for WhatsApp Web to finish loading...')
    saw_qr = False
    last_qr_log = -99
    last_load_log = -99
    tick = 0
    while True:
        tick += 1
        if page.is_closed():
            raise RuntimeError('WhatsApp tab closed while waiting for login')
        info = await _diag(page)
        try:
            full_text = await page.inner_text('body')
        except Exception:
            full_text = ' '.join(info.get('bodySample') or [])
        body = full_text or ' '.join(info.get('bodySample') or [])
        if info.get('dbError') or page_reports_db_error(body):
            log.error('[WhatsApp] database error is detected')
            log.error('[WhatsApp] final URL: %s', info.get('url') or page.url)
            log.error('[WhatsApp] target-group status: NOT OPENED')
            await _log_database_error(page, info, body, console_notes)
            raise DiagnosticStop('DATABASE ERROR DETECTED')
        names = await _chat_names(page)
        authenticated = bool(info.get('authenticated')) and not info.get('qr')
        if authenticated:
            db.set_stat('whatsapp', 'CONNECTED')
            log.info('[WhatsApp] Authentication detected')
            log.info('[WhatsApp] final URL: %s', info.get('url') or page.url)
            log.info('[WhatsApp] WhatsApp Web ready (%s chats visible)', len(names))
            log.info('[WhatsApp] Visible chats: %s', ', '.join(names[:25]) or '(titles not readable yet)')
            return names
        if info.get('qr') or info.get('qrLogin'):
            db.set_stat('whatsapp', 'QR')
            db.set_stat('target_group', 'WAITING_FOR_QR')
            if not saw_qr:
                log.info('[WhatsApp] QR/login UI is detected')
                log.info('[WhatsApp] final URL: %s', info.get('url') or page.url)
                log.info('[WhatsApp] target-group status: waiting for manual QR scan (not opened)')
                log.info('[WhatsApp] Browser left open for manual QR scan. No automatic login.')
                saw_qr = True
            if tick - last_qr_log >= 15:
                log.info('[WhatsApp] Waiting at QR screen (scan manually in this Chrome window)')
                last_qr_log = tick
        elif tick - last_load_log >= 8:
            log.info(
                '[WhatsApp] Still loading... url=%s pane=%s qr=%s dbError=%s chatUi=%s',
                info.get('url'), info.get('pane'), info.get('qr'), info.get('dbError'), info.get('chatUi'),
            )
            last_load_log = tick
        if not saw_qr and tick >= 180:
            log.error('[WhatsApp] Timed out waiting for chat list. final URL=%s diag=%s', page.url, await _diag(page))
            log.error('[WhatsApp] target-group status: NOT OPENED')
            raise RuntimeError('WhatsApp Web did not become ready')
        await page.wait_for_timeout(2000)


async def _log_database_error(page, info, body, console_notes):
    db.set_stat('whatsapp', 'DATABASE_ERROR')
    log.error('[WhatsApp] DATABASE ERROR DETECTED')
    log.error('[WhatsApp] Diagnostic information: url=%s title=%s', info.get('url'), info.get('title'))
    log.error('[WhatsApp] Diagnostic information: pane=%s qr=%s chatUi=%s webdriver=%s',
              info.get('pane'), info.get('qr'), info.get('chatUi'), info.get('webdriver'))
    try:
        probe = await page.evaluate(INDEXEDDB_PROBE_JS)
        log.error('[WhatsApp] Diagnostic information: IndexedDB probe=%s', probe)
    except Exception as exc:
        log.error('[WhatsApp] Diagnostic information: IndexedDB probe failed: %s', exc)
    try:
        ua = await page.evaluate('() => ({ ua: navigator.userAgent, webdriver: !!navigator.webdriver, langs: navigator.languages })')
        log.error('[WhatsApp] Diagnostic information: browser=%s', ua)
    except Exception as exc:
        log.error('[WhatsApp] Diagnostic information: browser probe failed: %s', exc)
    sample = ' | '.join((body or '').splitlines()[:8])
    log.error('[WhatsApp] Diagnostic information: page text sample: %s', sample[:400])
    if console_notes:
        log.error('[WhatsApp] Diagnostic information: console/page errors: %s', ' || '.join(console_notes[-12:]))
    log.error('[WhatsApp] Ingest stopped for diagnosis.')
    db.set_stat('last_error', 'DATABASE ERROR DETECTED; ingest stopped. See ingest.log')


async def _click_search(page):
    selectors = [
        'div[contenteditable="true"][data-tab="3"]',
        'div[contenteditable="true"][aria-label*="Search"]',
        'div[contenteditable="true"][data-tab="6"]',
        '#side div[contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        'button[aria-label*="Search"]',
        '[data-icon="search"]',
    ]
    for selector in selectors:
        loc = page.locator(selector).first
        try:
            if await loc.count() == 0:
                continue
            await loc.click(timeout=2500)
            return True
        except Exception:
            continue
    return False


async def _type_search(page, name):
    boxes = page.locator('#side div[contenteditable="true"], div[contenteditable="true"][data-tab="3"], div[contenteditable="true"][aria-label*="Search"]')
    count = await boxes.count()
    if count == 0:
        return False
    box = boxes.first
    await box.click()
    await page.keyboard.press('Control+A')
    await page.keyboard.press('Backspace')
    await box.type(name, delay=35)
    await page.wait_for_timeout(1500)
    return True


async def _header_matches(page, name):
    try:
        await page.wait_for_selector('#main header', timeout=6000)
    except Exception:
        pass
    header = await _header_title(page)
    return header, _header_is_target(header, name)


async def _click_visible_chat(page, name):
    locators = [
        page.get_by_title(name, exact=True).first,
        page.locator(f'#pane-side span[title="{name}"]').first,
        page.locator(f'#side span[title="{name}"]').first,
        page.locator(f'[role="listitem"] span[title="{name}"]').first,
        page.locator('[data-testid="cell-frame-title"]').filter(has_text=name).first,
        page.get_by_text(name, exact=True).first,
    ]
    for loc in locators:
        try:
            if await loc.count() == 0:
                continue
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=4000)
            log.info('[WhatsApp] Clicked chat via Playwright locator')
            return True
        except Exception as exc:
            log.info('[WhatsApp] Click locator failed: %s', exc)
    names = await _chat_names(page)
    for visible in names:
        if not _names_match(visible, name):
            continue
        loc = page.get_by_title(visible, exact=True).first
        try:
            if await loc.count():
                await loc.click(timeout=4000)
                log.info('[WhatsApp] Clicked visible chat %r', visible)
                return True
        except Exception:
            continue
        text_loc = page.get_by_text(visible, exact=True).first
        try:
            if await text_loc.count():
                await text_loc.click(timeout=4000)
                log.info('[WhatsApp] Clicked visible chat text %r', visible)
                return True
        except Exception:
            continue
    try:
        clicked = await page.evaluate(CLICK_CHAT_JS, name)
        if clicked and clicked.get('ok'):
            log.info('[WhatsApp] Clicked chat via DOM script (%s)', clicked.get('title'))
            return True
    except Exception as exc:
        log.info('[WhatsApp] DOM click failed: %s', exc)
    return False


async def _search_and_open(page, name):
    log.info('[WhatsApp] Group not in the current chat list, searching...')
    await _click_search(page)
    typed = await _type_search(page, name)
    if not typed:
        log.warning('[WhatsApp] Search box not found')
        return False
    await page.wait_for_timeout(1500)
    try:
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(800)
        header, ok = await _header_matches(page, name)
        if ok:
            log.info('[WhatsApp] Target group found')
            log.info('[WhatsApp] Opening group')
            return True
    except Exception:
        pass
    names = await _chat_names(page)
    log.info('[WhatsApp] Search results/chats: %s', ', '.join(names[:25]) or '(none)')
    if any(_names_match(visible, name) for visible in names):
        log.info('[WhatsApp] Target group found')
        log.info('[WhatsApp] Opening group')
    return await _click_visible_chat(page, name)


async def _scroll_chat_list(page, name):
    for _ in range(8):
        names = await _chat_names(page)
        if any(_names_match(visible, name) for visible in names):
            return True
        try:
            await page.evaluate(
                """() => {
                  const pane = document.querySelector('#pane-side') || document.querySelector('#side');
                  if (!pane) return;
                  const scroller = pane.querySelector('div[role="grid"]') || pane.querySelector('div[tabindex]') || pane;
                  scroller.scrollTop += 420;
                }"""
            )
        except Exception:
            return False
        await page.wait_for_timeout(400)
    return False


async def _open_group(page, name):
    log.info('[WhatsApp] Target group search started: %s', name)
    db.set_stat('target_group', 'SEARCHING')
    names = await _chat_names(page)
    info = await _diag(page)
    log.info('[WhatsApp] Visible chats (%s): %s', len(names), ', '.join(names[:25]) or '(none)')
    if info.get('paneText') and not names:
        log.info('[WhatsApp] Chat pane text sample: %s', ' | '.join(info.get('paneText')[:20]))

    opened = False
    present = any(_names_match(visible, name) for visible in names)
    if not present:
        present = await _scroll_chat_list(page, name)
        names = await _chat_names(page)
        present = any(_names_match(visible, name) for visible in names)
    if present:
        log.info('[WhatsApp] Target group found')
        log.info('[WhatsApp] Opening group')
        opened = await _click_visible_chat(page, name)
        header, ok = await _header_matches(page, name)
        if ok:
            db.set_stat('target_group', 'FOUND')
            db.set_stat('last_error', '')
            log.info('[WhatsApp] Target group opened: %s', header)
            log.info('[WhatsApp] Target group header verified: %s', header)
            return True
        log.warning('[WhatsApp] List click did not open the target header (got %r)', header)
        opened = False

    opened = await _search_and_open(page, name)
    header, ok = await _header_matches(page, name)
    if not opened or not ok:
        names = await _chat_names(page)
        db.set_stat('target_group', 'NOT FOUND')
        visible = ', '.join(names) if names else '(no chat titles readable)'
        sample = ' | '.join((info.get('paneText') or [])[:20])
        message = f'TARGET GROUP NOT FOUND: {name} | visible chats: {visible}'
        if sample and visible == '(no chat titles readable)':
            message += f' | pane text: {sample}'
        if header:
            message += f' | open header: {header}'
        log.error('[WhatsApp] %s', message)
        db.set_stat('last_error', message[:300])
        raise RuntimeError(message)

    db.set_stat('target_group', 'FOUND')
    db.set_stat('last_error', '')
    log.info('[WhatsApp] Target group opened: %s', header)
    log.info('[WhatsApp] Target group header verified: %s', header)
    return True


async def _collect_images(page):
    try:
        return await page.evaluate(COLLECT_IMAGES_JS) or []
    except Exception as exc:
        log.warning('[WhatsApp] Could not read images: %s', exc)
        return []


async def _download_image(page, src, message_id):
    data = await page.evaluate(DOWNLOAD_JS, src)
    raw = base64.b64decode(data)
    digest = hashlib.sha1((message_id + src[:40]).encode('utf-8')).hexdigest()[:12]
    stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    path = config.INCOMING_DIR / f'{stamp}-{digest}.jpg'
    path.write_bytes(raw)
    return path


async def watch_forever():
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError('Playwright is not installed. Run install.bat in tools/wa_booking_ingest') from exc

    from session import DiagnosticStop, INGEST_LAUNCH_ARGS, prepare_for_start

    config.ensure_dirs()
    group = (config.TARGET_WHATSAPP_GROUP or '').strip()
    log.info('[WhatsApp] TARGET_WHATSAPP_GROUP loaded as %r', group)
    if not group or group.lower() in ('your booking group name', 'changeme'):
        raise RuntimeError('Set TARGET_WHATSAPP_GROUP in .env to SMT On-call Support-Rac')

    prepare_for_start()
    console_notes = []

    def _note(kind, text):
        cleaned = re.sub(r'\s+', ' ', str(text or '')).strip()[:240]
        if not cleaned:
            return
        lowered = cleaned.lower()
        if any(word in lowered for word in ('cookie', 'token', 'authorization', 'secret', 'qr code', 'data-ref')):
            cleaned = '[redacted console message]'
        console_notes.append(f'{kind}: {cleaned}')
        if kind in ('error', 'pageerror'):
            log.warning('[WhatsApp] %s %s', kind, cleaned)

    log.info('[WhatsApp] Browser started')
    log.info('[WhatsApp] Browser channel: chrome')
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(config.PROFILE_DIR),
            channel='chrome',
            headless=config.HEADLESS,
            args=list(INGEST_LAUNCH_ARGS),
            viewport={'width': 1280, 'height': 900},
            locale='en-IN',
            timezone_id='Asia/Kolkata',
        )
        page = context.pages[0] if context.pages else await context.new_page()
        page.on('console', lambda msg: _note(msg.type, msg.text))
        page.on('pageerror', lambda err: _note('pageerror', err))
        if 'web.whatsapp.com' not in (page.url or ''):
            await page.goto('https://web.whatsapp.com/', wait_until='domcontentloaded')
        log.info('[WhatsApp] WhatsApp Web loaded (%s)', page.url)
        db.set_stat('whatsapp', 'LOADING')
        try:
            probe = await page.evaluate(INDEXEDDB_PROBE_JS)
            log.info('[WhatsApp] IndexedDB probe after load: %s', probe)
        except Exception as exc:
            log.warning('[WhatsApp] IndexedDB probe after load failed: %s', exc)
        await _wait_logged_in(page, console_notes)
        opened = False
        for attempt in range(8):
            try:
                await _open_group(page, group)
                opened = True
                break
            except DiagnosticStop:
                raise
            except Exception as exc:
                log.error('[WhatsApp] Open group attempt %s failed: %s', attempt + 1, exc)
                await page.wait_for_timeout(4000)
        if not opened:
            raise RuntimeError(f'TARGET GROUP NOT FOUND: {group}')
        if config.SKIP_EXISTING_ON_START:
            existing = await _collect_images(page)
            for item in existing:
                mid = item.get('id') or hashlib.sha1((item.get('src') or '').encode()).hexdigest()
                if mid and not db.message_seen(mid):
                    db.mark_message(mid, group, '', 'skipped_startup', 'already on screen at start')
            log.info('[WhatsApp] Ignoring %s image(s) already in the open chat', len(existing))
        db.set_stat('target_group', 'WATCHING')
        log.info('[WhatsApp] Watching for new booking images...')
        while True:
            if page.is_closed():
                raise RuntimeError('WhatsApp tab closed')
            info = await _diag(page)
            if info.get('dbError'):
                body = ' '.join(info.get('bodySample') or [])
                await _log_database_error(page, info, body, console_notes)
                raise DiagnosticStop('DATABASE ERROR DETECTED')
            header = await _header_title(page)
            if header and not _header_is_target(header, group):
                log.warning('[WhatsApp] Left target chat (%r). Re-opening %s', header, group)
                await _open_group(page, group)
            items = await _collect_images(page)
            for item in items:
                mid = item.get('id') or hashlib.sha1((item.get('src') or '').encode()).hexdigest()
                if not mid or db.message_seen(mid):
                    continue
                log.info('[WhatsApp] New image detected %s', mid)
                db.set_stat('last_image', datetime.utcnow().isoformat(timespec='seconds') + 'Z')
                path = await _download_image(page, item['src'], mid)
                log.info('[WhatsApp] Image downloaded: %s', path.name)
                db.mark_message(mid, group, str(path), 'queued', '')
                db.enqueue_job('ocr_image', {
                    'image_path': str(path),
                    'message_id': mid,
                    'group_name': group,
                })
            db.set_stat('whatsapp', 'CONNECTED')
            await page.wait_for_timeout(config.POLL_SECONDS * 1000)
