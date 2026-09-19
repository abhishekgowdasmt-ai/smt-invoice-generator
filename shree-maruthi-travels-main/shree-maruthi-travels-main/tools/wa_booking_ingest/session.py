"""Dedicated Playwright WhatsApp session for this ingest tool only.

Never touches the user's normal Chrome profile or other WhatsApp installs.
Does not automatically reset or recreate profiles.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from logutil import log

MARKER_NAME = 'INGEST_WHATSAPP_PROFILE.txt'
LOCK_NAMES = ('SingletonLock', 'SingletonCookie', 'SingletonSocket', 'DevToolsActivePort')
DB_ERROR_RE = re.compile(
    r'database error occurred|relink your device|please relink',
    re.I,
)
WHATSAPP_IDB = Path('Default') / 'IndexedDB' / 'https_web.whatsapp.com_0.indexeddb.leveldb'
CHROME_USER_DATA_MARKERS = (
    r'Google\Chrome\User Data',
    'Google/Chrome/User Data',
)
INGEST_LAUNCH_ARGS = (
    '--disable-dev-shm-usage',
    '--disable-session-crashed-bubble',
    '--hide-crash-restore-bubble',
)


class DiagnosticStop(RuntimeError):
    """Fatal WhatsApp/browser diagnostic stop. Do not retry or reset the profile."""


def profile_dir():
    return Path(config.PROFILE_DIR)


def _stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def _write_marker(folder):
    marker = Path(folder) / MARKER_NAME
    if marker.exists():
        return
    marker.write_text(
        'Dedicated Playwright profile for SMT WhatsApp booking ingest.\n'
        'This is NOT your normal Chrome profile.\n'
        f'Created {datetime.now().isoformat(timespec="seconds")}\n',
        encoding='utf-8',
    )


def whatsapp_idb_dir(folder=None):
    return Path(folder or profile_dir()) / WHATSAPP_IDB


def profile_has_whatsapp_db(folder=None):
    folder = Path(folder or profile_dir())
    idb = whatsapp_idb_dir(folder)
    if idb.exists():
        return True
    indexed = folder / 'Default' / 'IndexedDB'
    if not indexed.exists():
        return False
    return any('whatsapp' in path.name.lower() for path in indexed.iterdir())


def page_reports_db_error(text):
    return bool(DB_ERROR_RE.search(text or ''))


def is_forbidden_chrome_profile(folder):
    text = str(Path(folder))
    return any(marker in text for marker in CHROME_USER_DATA_MARKERS)


def _dir_is_writable(folder):
    folder = Path(folder)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / '.ingest_write_probe'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        return True
    except OSError:
        return False


def _list_chromium_processes():
    script = (
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Name -match 'chrome|chromium' } | "
        "Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ['powershell', '-NoProfile', '-Command', script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning('[WhatsApp] Could not list Chromium processes: %s', exc)
        return []
    raw = (completed.stdout or '').strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    rows = []
    for item in data or []:
        rows.append({
            'pid': int(item.get('ProcessId') or 0),
            'name': str(item.get('Name') or ''),
            'command': str(item.get('CommandLine') or ''),
        })
    return rows


def processes_using_profile(folder=None):
    folder = str(Path(folder or profile_dir()).resolve()).lower()
    alt = folder.replace('\\', '/')
    matches = []
    for row in _list_chromium_processes():
        command = (row.get('command') or '').lower()
        if folder in command or alt in command:
            matches.append(row)
    return matches


def kill_stale_browsers(folder=None):
    """Stop Chromium processes that use THIS ingest profile only."""
    matches = processes_using_profile(folder)
    killed = []
    for row in matches:
        pid = row.get('pid')
        if not pid:
            continue
        try:
            subprocess.run(
                ['powershell', '-NoProfile', '-Command', f'Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue'],
                capture_output=True,
                text=True,
                timeout=15,
            )
            killed.append(str(pid))
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            log.warning('[WhatsApp] Could not stop ingest Chromium pid %s: %s', pid, exc)
    if killed:
        log.info('[WhatsApp] Closed stale ingest Chromium process(es): %s', ', '.join(killed))
        time.sleep(1.0)
    return killed


def backup_profile(reason, folder=None, recreate=True):
    """Manual backup helper. Watcher/startup must not call this automatically."""
    folder = Path(folder or profile_dir())
    if not folder.exists():
        log.info('[WhatsApp] No session folder to back up at %s', folder)
        return None
    dest = folder.parent / f'{folder.name}.corrupt-{_stamp()}'
    n = 1
    while dest.exists():
        n += 1
        dest = folder.parent / f'{folder.name}.corrupt-{_stamp()}-{n}'
    log.warning('[WhatsApp] Backing up ingest session %s -> %s (%s)', folder, dest, reason)
    try:
        folder.rename(dest)
    except OSError:
        shutil.copytree(folder, dest)
        shutil.rmtree(folder, ignore_errors=True)
    note = dest / 'CORRUPTION_NOTE.txt'
    note.write_text(f'{reason}\nbacked_up={datetime.now().isoformat(timespec="seconds")}\n', encoding='utf-8')
    if recreate:
        folder.mkdir(parents=True, exist_ok=True)
        _write_marker(folder)
        log.info('[WhatsApp] Fresh ingest session folder created at %s', folder)
    return dest


def remove_stale_locks(folder=None):
    folder = Path(folder or profile_dir())
    if not folder.exists():
        return []
    removed = []
    for name in LOCK_NAMES:
        path = folder / name
        if path.exists() or path.is_symlink():
            try:
                path.unlink()
                removed.append(name)
            except OSError as exc:
                log.warning('[WhatsApp] Could not remove lock %s: %s', path, exc)
    if removed:
        log.info('[WhatsApp] Removed stale Chromium locks: %s', ', '.join(removed))
    return removed


def playwright_version():
    try:
        import playwright
        return getattr(playwright, '__version__', 'unknown')
    except Exception:
        return 'unavailable'


def chromium_executable_hint():
    home = Path.home()
    candidates = list((home / 'AppData' / 'Local' / 'ms-playwright').glob('chromium-*/chrome-win64/chrome.exe'))
    return str(candidates[-1]) if candidates else ''


def log_prelaunch_diagnostics(folder=None, launch_args=None):
    folder = Path(folder or profile_dir()).resolve()
    log.info('[WhatsApp] Playwright version: %s', playwright_version())
    chrome = chromium_executable_hint()
    if chrome:
        log.info('[WhatsApp] Chromium executable hint: %s', chrome)
    log.info('[WhatsApp] user_data_dir: %s', folder)
    log.info('[WhatsApp] user_data_dir exists: %s', folder.exists())
    log.info('[WhatsApp] user_data_dir writable: %s', _dir_is_writable(folder))
    log.info('[WhatsApp] forbidden Chrome User Data path: %s', is_forbidden_chrome_profile(folder))
    log.info('[WhatsApp] python: %s', sys.executable)
    log.info('[WhatsApp] launch args: %s', list(launch_args or INGEST_LAUNCH_ARGS))
    using = processes_using_profile(folder)
    if using:
        summary = ', '.join(f"{row['name']}:{row['pid']}" for row in using)
        log.warning('[WhatsApp] Chromium already using ingest profile: %s', summary)
    else:
        log.info('[WhatsApp] No other Chromium process is using the ingest profile')
    idb = whatsapp_idb_dir(folder)
    log.info('[WhatsApp] WhatsApp IndexedDB dir exists: %s', idb.exists())


def prepare_for_start():
    """Prepare to launch. Does not rename or recreate the session profile."""
    config.ensure_dirs()
    current = profile_dir().resolve()
    log.info('[WhatsApp] Ingest session directory: %s', current)
    if is_forbidden_chrome_profile(current):
        raise RuntimeError('WHATSAPP_PROFILE_DIR points at the normal Chrome profile. Use the ingest folder only.')
    kill_stale_browsers(current)
    current.mkdir(parents=True, exist_ok=True)
    _write_marker(current)
    remove_stale_locks(current)
    log_prelaunch_diagnostics(current)
    return current


def reset_session(reason='manual reset'):
    """Manual only. Not used by watcher startup."""
    kill_stale_browsers()
    time.sleep(0.5)
    remove_stale_locks()
    dest = backup_profile(reason)
    log.info('[WhatsApp] Manual session reset complete.')
    return dest
