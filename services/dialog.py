"""
Tkinter folder-drop dialog.
"""
from __future__ import annotations

import threading
from pathlib import Path

try:
    import tkinter as tk
    import tkinter.messagebox as mb
    _TK_AVAILABLE = True
except ModuleNotFoundError:
    _TK_AVAILABLE = False

from core.config import DIALOG_TIMEOUT

CHOICE_WITH_FOLDER = "with_folder"
CHOICE_CONTENTS    = "contents"
CHOICE_SKIP        = "skip"

_dialog_sem = threading.Semaphore(1)


def ask_folder_choice(folder_path: str, label: str) -> str:
    result = {"value": CHOICE_SKIP}
    if not _TK_AVAILABLE:
        return CHOICE_SKIP
    with _dialog_sem:
        def build():
            root = tk.Tk()
            root.title("GDrive Sync — New Folder Detected")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            root.lift(); root.focus_force()

            BG      = "#1e1e2e"; PANEL = "#2a2a3e"; ACCENT = "#4f9ef8"
            TEXT    = "#e0e0f0"; SUBTEXT = "#9090b0"
            GREEN   = "#3a9a50"; GREEN_H = "#4ab060"
            BLUE_H  = "#5aafff"; GRAY = "#555577"; GRAY_H = "#6666aa"
            WARN    = "#f8c44f"

            root.configure(bg=BG)
            W, H = 560, 390
            root.update_idletasks()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

            tk.Frame(root, bg=ACCENT, height=5).pack(fill="x")
            tk.Label(root, text="📁", font=("Segoe UI Emoji", 30),
                     bg=BG, fg=WARN).pack(pady=(14, 2))
            tk.Label(root, text="New Folder Detected",
                     font=("Segoe UI Semibold", 13), bg=BG, fg=TEXT).pack()
            tk.Label(root, text=f'"{Path(folder_path).name}"  in  [{label}]',
                     font=("Consolas", 10), bg=BG, fg=ACCENT).pack(pady=(3, 2))
            tk.Label(root, text=f"Full path: {folder_path}",
                     font=("Segoe UI", 8), bg=BG, fg=SUBTEXT).pack(pady=(0, 4))
            tk.Label(root, text="How should this folder be uploaded to Google Drive?",
                     font=("Segoe UI", 10), bg=BG, fg=SUBTEXT).pack(pady=(0, 8))

            cdv  = tk.StringVar(value=f"Auto-skip in {DIALOG_TIMEOUT}s")
            tk.Label(root, textvariable=cdv, font=("Segoe UI", 8),
                     bg=BG, fg=SUBTEXT).pack(pady=(0, 10))

            bf   = tk.Frame(root, bg=BG); bf.pack()
            done = threading.Event()

            def choose(v):
                result["value"] = v; done.set(); root.destroy()

            def make_btn(par, ico, title, sub, bc, hc, cmd):
                outer = tk.Frame(par, bg=bc, padx=1, pady=1)
                inner = tk.Frame(outer, bg=PANEL)
                inner.pack(fill="both", expand=True, padx=1, pady=1)
                r1 = tk.Label(inner, text=f"{ico}  {title}",
                              font=("Segoe UI Semibold", 10),
                              bg=PANEL, fg=TEXT, padx=12, pady=6)
                r1.pack()
                r2 = tk.Label(inner, text=sub, font=("Segoe UI", 8),
                              bg=PANEL, fg=SUBTEXT)
                r2.pack(pady=(0, 8))
                def en(e):
                    for w in (inner, r1, r2): w.configure(bg=hc)
                def le(e):
                    for w in (inner, r1, r2): w.configure(bg=PANEL)
                for w in (outer, inner, r1, r2):
                    w.bind("<Enter>", en); w.bind("<Leave>", le)
                    w.bind("<Button-1>", lambda e, c=cmd: c())
                outer.pack(side="left", padx=6)

            make_btn(bf, "📂", "Upload with Folder", "Creates folder on GDrive",
                     ACCENT, BLUE_H, lambda: choose(CHOICE_WITH_FOLDER))
            make_btn(bf, "📄", "Upload Contents Only", "Flattens files into parent",
                     GREEN, GREEN_H, lambda: choose(CHOICE_CONTENTS))
            make_btn(bf, "⛔", "Skip", "Ignore this folder",
                     GRAY, GRAY_H, lambda: choose(CHOICE_SKIP))

            rem = [DIALOG_TIMEOUT]
            def tick():
                if done.is_set(): return
                rem[0] -= 1
                if rem[0] <= 0:
                    cdv.set("Skipping…"); choose(CHOICE_SKIP); return
                cdv.set(f"Auto-skip in {rem[0]}s")
                root.after(1000, tick)
            root.after(1000, tick)
            root.protocol("WM_DELETE_WINDOW", lambda: choose(CHOICE_SKIP))
            root.mainloop()

        t = threading.Thread(target=build, daemon=True)
        t.start(); t.join()
    return result["value"]
