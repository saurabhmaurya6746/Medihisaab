"""Pharmacy POS - Standalone Desktop Window Shell.

Launches the Pharmacy POS user interface inside a dedicated native Windows
desktop window (backed by Microsoft Edge WebView2 via pywebview WinForms backend),
avoiding browser tabs, URL address bars, or standard browser chrome.
If pywebview is unavailable, launches Microsoft Edge / Chrome in dedicated
app mode (--app=http://...). It never opens a normal browser tab. If no
desktop host is available, it exits with an actionable error instead.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

APP_TITLE = "MediHisaab — Offline Pharmacy Management System"
DEFAULT_URL = "http://127.0.0.1:38291"
DEFAULT_WIDTH = 1366
DEFAULT_HEIGHT = 860
DEFAULT_MIN_WIDTH = 1024
DEFAULT_MIN_HEIGHT = 700


def wait_for_daemon(url: str, timeout: float = 15.0) -> bool:
    """Wait for local backend daemon to answer health check."""
    health_url = url.rstrip("/") + "/health"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(
                health_url,
                headers={"User-Agent": "MediHisaab-DesktopWindow/1.0"},
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def launch_native_webview(url: str, width: int, height: int) -> bool:
    """Launch native window via pywebview using Microsoft Edge WebView2 (WinForms)."""
    try:
        import webview

        # Configure WebView2 storage path if writable
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            storage_path = Path(local_app_data) / "PharmacyApp" / "webview_cache"
            try:
                storage_path.mkdir(parents=True, exist_ok=True)
                os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(storage_path)
            except Exception:
                pass

        window = webview.create_window(
            title=APP_TITLE,
            url=url,
            width=width,
            height=height,
            min_size=(DEFAULT_MIN_WIDTH, DEFAULT_MIN_HEIGHT),
            resizable=True,
            confirm_close=False,
            easy_drag=False,
        )
        def set_window_icon():
            """Apply MediHisaab icon to all open WinForms windows."""
            try:
                import clr
                import System.Drawing
                from System.Windows.Forms import Application

                base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
                candidates = [
                    base_dir / "medihisaab-icon.ico",
                    base_dir / "assets" / "medihisaab-icon.ico",
                    base_dir.parent / "assets" / "medihisaab-icon.ico",
                ]
                icon_path = None
                for c in candidates:
                    if c.is_file():
                        icon_path = str(c)
                        break

                if icon_path:
                    icon = System.Drawing.Icon(icon_path)
                    for form in Application.OpenForms:
                        form.Icon = icon
            except Exception:
                pass

        # Run using winforms GUI (standard Windows desktop forms with WebView2)
        webview.start(set_window_icon, gui="winforms", debug=False)
        return True
    except Exception as e:
        print(f"[WARN] Native WebView2 host could not start: {e}", file=sys.stderr)
        return False


def launch_desktop_app_window(url: str) -> bool:
    """Fallback: Launch Microsoft Edge or Chrome in isolated --app window mode."""
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    ]

    for exe in edge_paths:
        if exe and os.path.exists(exe):
            cmd = [
                exe,
                f"--app={url}",
                f"--window-size={DEFAULT_WIDTH},{DEFAULT_HEIGHT}",
                "--disable-features=TranslateUI",
                "--no-first-run",
            ]
            try:
                subprocess.Popen(cmd)
                return True
            except Exception:
                continue

    return False


def main():
    parser = argparse.ArgumentParser(description="MediHisaab Native Desktop Window Shell")
    parser.add_argument("--url", default=DEFAULT_URL, help="Pharmacy daemon web URL")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Initial window width")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Initial window height")
    parser.add_argument("--wait", action="store_true", help="Wait for daemon to become ready before displaying window")
    args = parser.parse_args()

    if args.wait:
        ready = wait_for_daemon(args.url, timeout=20.0)
        if not ready:
            print(f"[WARN] Local daemon service did not respond within 20s at {args.url}", file=sys.stderr)

    # 1. Attempt native WebView2 window via pywebview
    success = launch_native_webview(args.url, args.width, args.height)
    if success:
        return 0

    # 2. Fallback to native --app window
    print("[INFO] Falling back to dedicated desktop app window...", file=sys.stderr)
    success = launch_desktop_app_window(args.url)
    if success:
        return 0

    print(
        "[ERROR] Could not open the desktop window. Install or repair Microsoft Edge/WebView2, "
        "then relaunch Pharmacy POS. No browser tab was opened.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
