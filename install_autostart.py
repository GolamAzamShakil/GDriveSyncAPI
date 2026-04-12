"""
install_autostart.py
====================
Installs (or uninstalls) GDrive Sync as a Windows scheduled task
so it starts automatically at system boot / user logon.

Usage
-----
  IMPORTANT: Run this script with your venv ACTIVATED:
      syncAPIVenv\\Scripts\\activate
      python install_autostart.py install

  Install  (tray mode — runs at YOUR logon, no admin needed):
      python install_autostart.py install

  Install  (headless — runs at boot as SYSTEM, requires admin):
      python install_autostart.py install --headless

  Uninstall:
      python install_autostart.py uninstall

  Check status:
      python install_autostart.py status

How it works
------------
Uses Windows Task Scheduler (schtasks.exe).
The task launches the venv's own pythonw.exe so all installed
packages (fastapi, uvicorn, pystray, etc.) are available.

The task is named "GDriveSyncAPI" and visible in Task Scheduler GUI
under Task Scheduler Library.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

TASK_NAME = "GDriveSyncAPI"
APP_NAME = "GDrive Sync API"
SCRIPT_DIR = Path(__file__).resolve().parent
MAIN_PY = SCRIPT_DIR / "main.py"
LOG_DIR = Path(os.environ.get("LOG_FILE", r"C:\Python314\Scripts\customScript\gdrive_sync.log")).parent
API_PORT = int(os.environ.get("API_PORT", "8000"))


# ═══════════════════════════════════════════════════════════════════
#  Venv detection
# ═══════════════════════════════════════════════════════════════════


def _detect_venv() -> dict:
    """
    Return info about the current Python environment.

    Returns a dict with:
        in_venv      bool   — True if a venv is active
        python_exe   Path   — python.exe in this environment
        pythonw_exe  Path   — pythonw.exe in this environment (may not exist)
        venv_root    Path   — root of the venv (or sys.prefix for system Python)
        is_system    bool   — True if this is the bare system Python
    """
    exe = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()
    base = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()
    in_venv = prefix != base

    # pythonw.exe lives next to python.exe in a venv
    pythonw = exe.with_name("pythonw.exe")
    if not pythonw.exists():
        # Some venvs put it under Scripts/
        pythonw = prefix / "Scripts" / "pythonw.exe"

    return {
        "in_venv": in_venv,
        "python_exe": exe,
        "pythonw_exe": pythonw if pythonw.exists() else exe,
        "venv_root": prefix,
        "is_system": not in_venv,
    }


def _assert_venv_or_warn() -> dict:
    """
    Warn loudly if the script is not running inside a venv,
    then return the env info dict regardless (caller decides whether to abort).
    """
    info = _detect_venv()
    if info["is_system"]:
        print()
        print("=" * 65)
        print("  ⚠  WARNING: You are NOT running inside a virtual environment.")
        print()
        print("  The Task Scheduler task will launch:")
        print(f"     {info['pythonw_exe']}")
        print()
        print("  This is your SYSTEM Python. If your packages (fastapi,")
        print("  uvicorn, pystray …) are only installed in a venv, the")
        print("  task will crash at startup with ModuleNotFoundError.")
        print()
        print("  To fix: activate your venv first, then re-run this script:")
        print(f"     {SCRIPT_DIR}\\syncAPIVenv\\Scripts\\activate")
        print(f"     python install_autostart.py install")
        print("=" * 65)
        print()
        answer = input("Continue anyway? [y/N]: ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)
    else:
        print(f"[OK]  Venv detected: {info['venv_root']}")
        print(f"      Interpreter  : {info['pythonw_exe']}")
    return info


# ═══════════════════════════════════════════════════════════════════
#  schtasks helpers
# ═══════════════════════════════════════════════════════════════════


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _task_exists() -> bool:
    r = _run(["schtasks", "/query", "/tn", TASK_NAME], check=False)
    return r.returncode == 0


def _api_reachable() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://localhost:{API_PORT}/health", timeout=3
        ) as r:
            return r.status == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
#  Install
# ═══════════════════════════════════════════════════════════════════


def install(headless: bool = False) -> None:
    if sys.platform != "win32":
        print("[ERROR] Windows only. See --help for Linux/macOS alternatives.")
        sys.exit(1)

    env = _assert_venv_or_warn()

    if _task_exists():
        print(f"\n[INFO] Task '{TASK_NAME}' already exists.")
        print("       Run 'uninstall' first if you want to re-register it.")
        status()
        return

    if headless:
        # SYSTEM account — runs at boot, no tray, requires admin
        python_exe = env["python_exe"]  # pythonw has no console anyway
        trigger_arg = ["/sc", "ONSTART"]
        runas_args = ["/ru", "SYSTEM"]
        mode_note = "headless  (SYSTEM account, boot trigger — requires Administrator)"
    else:
        # Current user — runs at logon, tray visible
        python_exe = env["pythonw_exe"]  # NO console window
        trigger_arg = ["/sc", "ONLOGON"]
        try:
            username = os.getlogin()
        except Exception:
            username = os.environ.get("USERNAME", "")
        runas_args = ["/ru", username] if username else []
        mode_note = f"tray mode  (user '{username}', logon trigger)"

    # The action: cd into project dir, then run pythonw main.py
    # We wrap in cmd /c so the working directory is set correctly.
    # This matters because main.py does relative imports.
    action = f'cmd /c "cd /d "{SCRIPT_DIR}" && ' f'"{python_exe}" "{MAIN_PY}""'

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    cmd = (
        [
            "schtasks",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            action,
            "/rl",
            "HIGHEST",
            "/f",  # overwrite silently if exists
            "/delay",
            "0000:30",  # 30 s startup delay (network settle)
        ]
        + trigger_arg
        + runas_args
    )

    print(f"\n[INFO] Installing task: {mode_note}")
    print(f"       Command : {action}")

    try:
        _run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"\n[ERROR] schtasks failed (rc={exc.returncode}):")
        print(exc.stderr.strip())
        if "Access is denied" in exc.stderr:
            print("\n[HINT] Run this script as Administrator for SYSTEM/boot tasks.")
        sys.exit(1)

    print(f"\n[OK]  Task '{TASK_NAME}' registered successfully.\n")

    if headless:
        print("Next steps:")
        print("  • Reboot, or run immediately:")
        print(f"      schtasks /run /tn {TASK_NAME}")
        print(f"  • API will be at  http://localhost:{API_PORT}")
        print("  • No tray icon — use the REST API or Task Scheduler to manage.")
    else:
        print("Next steps:")
        print("  • Log off and back in, or run immediately:")
        print(f"      schtasks /run /tn {TASK_NAME}")
        print("  • Watch for the GDrive Sync icon in the system tray (bottom-right).")
        print("  • Right-click tray icon → 'Open Dashboard' to open the API.")

    print()
    print(f"  Manage : Task Scheduler GUI → Task Scheduler Library → {TASK_NAME}")
    print(f"  Remove : python install_autostart.py uninstall")


# ═══════════════════════════════════════════════════════════════════
#  Uninstall
# ═══════════════════════════════════════════════════════════════════


def uninstall() -> None:
    if not _task_exists():
        print(f"[INFO] Task '{TASK_NAME}' does not exist — nothing to remove.")
        return
    try:
        _run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], check=True)
        print(f"[OK]  Task '{TASK_NAME}' removed.")
        print("      GDrive Sync will no longer start automatically.")
        print(f'      To start manually:  pythonw.exe "{MAIN_PY}"')
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Could not remove task (rc={exc.returncode}):")
        print(exc.stderr.strip())
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
#  Status
# ═══════════════════════════════════════════════════════════════════


def status() -> None:
    # Task Scheduler entry
    if not _task_exists():
        print(f"[INFO] Task '{TASK_NAME}' is NOT registered.")
        print(f"       Run:  python install_autostart.py install")
    else:
        result = _run(
            ["schtasks", "/query", "/tn", TASK_NAME, "/v", "/fo", "LIST"],
            check=False,
        )
        print(result.stdout)

    # Live API health
    url = f"http://localhost:{API_PORT}/health"
    print(f"Checking API at {url} …", end="  ")
    if _api_reachable():
        print("✅  ONLINE")
    else:
        print("❌  OFFLINE  (not reachable — is the task running?)")

    # Venv info
    print()
    env = _detect_venv()
    if env["in_venv"]:
        print(f"Current venv : {env['venv_root']}")
        print(f"Interpreter  : {env['pythonw_exe']}")
    else:
        print("⚠  No venv active — system Python is in use.")


# ═══════════════════════════════════════════════════════════════════
#  Help
# ═══════════════════════════════════════════════════════════════════


def _print_help() -> None:
    print(
        textwrap.dedent(
            f"""
    {APP_NAME} — Autostart Installer
    ====================================

    IMPORTANT — always run with your venv activated:
        {SCRIPT_DIR}\\syncAPIVenv\\Scripts\\activate
        python install_autostart.py <command>

    Commands:
      install            Register as a logon task (tray mode, current user)
      install --headless Register as a boot task  (SYSTEM, no tray, needs admin)
      uninstall          Remove the scheduled task
      status             Show task details + live API health check

    Modes explained
    ---------------
    Tray mode (default — recommended for desktop PCs)
      • Task runs as YOUR user account
      • Starts when you log in to Windows
      • System tray icon shows API health, host:port, open-in-browser
      • No admin rights needed to install

    Headless mode (for always-on PCs / servers)
      • Task runs as the SYSTEM account
      • Starts when Windows boots — before anyone logs in
      • No tray icon; manage via REST API at http://localhost:{API_PORT}
      • Requires running this installer as Administrator

    Venv and Task Scheduler
    -----------------------
    Task Scheduler does NOT activate your venv automatically.
    This installer works around that by pointing the task directly at
    the venv's pythonw.exe, so all your installed packages are available
    without needing to activate the venv in the task command.

    If you move or rename the venv, re-run this installer to update the task.

    Task name : {TASK_NAME}
    Manage    : Task Scheduler GUI → Task Scheduler Library → {TASK_NAME}
    """
        )
    )


# ═══════════════════════════════════════════════════════════════════
#  Linux/macOS hint
# ═══════════════════════════════════════════════════════════════════


def _print_linux_hint() -> None:
    py = sys.executable
    user = os.environ.get("USER", "youruser")
    print(
        textwrap.dedent(
            f"""
    Linux — systemd service
    -----------------------
    Create /etc/systemd/system/gdrive-sync.service :

        [Unit]
        Description=GDrive Sync API
        After=network.target

        [Service]
        Type=simple
        User={user}
        WorkingDirectory={SCRIPT_DIR}
        ExecStart={py} {MAIN_PY}
        Restart=on-failure
        RestartSec=10

        [Install]
        WantedBy=multi-user.target

    Then:
        sudo systemctl daemon-reload
        sudo systemctl enable --now gdrive-sync
        sudo systemctl status gdrive-sync

    macOS — launchd
    ---------------
    Create ~/Library/LaunchAgents/com.gdrivesync.plist
    See: https://www.launchd.info
    """
        )
    )


# ═══════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="install_autostart.py",
        description=f"{APP_NAME} autostart installer",
        add_help=False,
    )
    parser.add_argument(
        "command",
        choices=["install", "uninstall", "status", "help"],
        nargs="?",
        default="help",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Install as SYSTEM account (no tray, requires Administrator)",
    )
    args = parser.parse_args()

    if args.command == "install":
        if sys.platform != "win32":
            print("[ERROR] Windows only.")
            _print_linux_hint()
            sys.exit(1)
        install(headless=args.headless)

    elif args.command == "uninstall":
        if sys.platform != "win32":
            print("[ERROR] Windows only.")
            sys.exit(1)
        uninstall()

    elif args.command == "status":
        status()

    else:
        _print_help()
        if sys.platform != "win32":
            _print_linux_hint()


if __name__ == "__main__":
    main()
