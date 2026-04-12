"""
  • Icon colour reflects API state  (green / blue / red / grey)
  • "✅ API running — localhost:8000"  live status line
  • "🌐 Open Dashboard (localhost:8000)"  — opens browser on click
  • "📋 Copy API URL"  — copies URL to clipboard
  • "📄 Open API Docs"  — opens /docs in browser
  • Many more
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser

try:
    import pystray
    from pystray import MenuItem as Item
    from PIL import Image, ImageDraw

    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

from core.api_status import API_STATUS
from core.config import APP_NAME, LOG_FILE
from core.logging_setup import log
from core.schedule import SCHEDULE
from core.state import PROGRESS, _shutdown, is_paused, pause, request_force_poll, resume
from services.settings_window import open_settings_window

def _make_icon(color: str = "#4CAF50") -> "Image.Image":
    """
    64×64 RGBA status-light icon.
    Coloured outer ring → white ring → coloured inner dot.
    Readable even at 16×16 (Windows notification area).
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dc = ImageDraw.Draw(img)
    dc.ellipse([2, 2, 62, 62], fill=color)
    dc.ellipse([10, 10, 54, 54], fill="white")
    dc.ellipse([18, 18, 46, 46], fill=color)
    dc.ellipse([24, 24, 40, 40], fill="white")
    return img


def _make_icon_for_state() -> "Image.Image":
    return _make_icon(API_STATUS.tray_icon_color())


def _copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["clip"], input=text, text=True, capture_output=True, timeout=5
            )
            return True
        if sys.platform == "darwin":
            subprocess.run(
                ["pbcopy"], input=text, text=True, capture_output=True, timeout=5
            )
            return True
        for cmd in (
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                r = subprocess.run(
                    cmd, input=text, text=True, capture_output=True, timeout=5
                )
                if r.returncode == 0:
                    return True
            except FileNotFoundError:
                continue
    except Exception as exc:
        log.debug(f"Clipboard copy failed: {exc}")
    return False


def run_tray() -> None:
    if not _TRAY_AVAILABLE:
        log.warning("pystray / PIL not installed — tray disabled.")
        return

    def on_pause_resume(icon, item):
        if is_paused():
            resume()
            log.info("Sync resumed.")
        else:
            pause()
            log.info("Sync paused.")

    def on_scan_now(icon, item):
        request_force_poll()
        log.info("Manual scan triggered from tray.")

    def on_settings(icon, item):
        open_settings_window(icon)

    def on_quit(icon, item):
        log.info("Quit via tray.")
        _shutdown.set()
        pause()
        icon.stop()

    def on_open_dashboard(icon, item):
        webbrowser.open(API_STATUS.url)
        log.info(f"Opened dashboard: {API_STATUS.url}")

    def on_open_docs(icon, item):
        webbrowser.open(API_STATUS.docs_url)
        log.info(f"Opened API docs: {API_STATUS.docs_url}")

    def on_copy_url(icon, item):
        _copy_to_clipboard(API_STATUS.url)
        log.info(f"Copied API URL: {API_STATUS.url}")

    def lbl_api_status(item):
        return API_STATUS.tray_status_line()

    def lbl_open_dashboard(item):
        return f"🌐  Open Dashboard  ({API_STATUS.url})"

    def lbl_open_docs(item):
        return f"📄  API Docs  ({API_STATUS.docs_url})"

    def lbl_copy_url(item):
        return f"📋  Copy API URL"

    def lbl_pause(item):
        return "▶  Resume Sync" if is_paused() else "⏸  Pause Sync"

    def lbl_progress(item):
        return PROGRESS.label_progress() or ""

    def lbl_remaining(item):
        return PROGRESS.label_remaining()

    def lbl_countdown(item):
        return f"🕐  {SCHEDULE.countdown_label()}"

    def progress_visible(item):
        return PROGRESS.label_progress() is not None

    def remaining_enabled(item):
        return PROGRESS.has_remaining()

    def dashboard_enabled(item):
        return API_STATUS.is_healthy

    menu = pystray.Menu(
        Item(lbl_api_status, lambda *_: None, enabled=False),
        pystray.Menu.SEPARATOR,
        Item(lbl_open_dashboard, on_open_dashboard, enabled=dashboard_enabled),
        Item(lbl_open_docs, on_open_docs, enabled=dashboard_enabled),
        Item(lbl_copy_url, on_copy_url),
        pystray.Menu.SEPARATOR,

        Item(lbl_pause, on_pause_resume),
        Item("🔍  Scan Now", on_scan_now),
        Item("⚙  Schedule…", on_settings),
        pystray.Menu.SEPARATOR,

        Item(lbl_progress, lambda *_: None, enabled=False, visible=progress_visible),
        Item(lbl_remaining, lambda *_: None, enabled=remaining_enabled),
        pystray.Menu.SEPARATOR,

        Item(lbl_countdown, lambda *_: None, enabled=False),
        pystray.Menu.SEPARATOR,

        Item("📁  View Log", lambda icon, item: os.startfile(LOG_FILE)),
        pystray.Menu.SEPARATOR,
        Item("❌  Quit", on_quit),
    )

    icon = pystray.Icon(
        name=APP_NAME,
        icon=_make_icon_for_state(),
        title=f"{APP_NAME} — Starting…",
        menu=menu,
    )

    def refresh_loop():
        while not _shutdown.is_set():
            time.sleep(1)
            try:
                paused = is_paused()
                suffix = " — Paused" if paused else " — Running"
                icon.icon = _make_icon_for_state()
                icon.title = f"{APP_NAME}{suffix}  |  {API_STATUS.url}"
                icon.update_menu()
            except Exception:
                pass

    threading.Thread(target=refresh_loop, daemon=True, name="TrayRefresh").start()

    icon.run()
