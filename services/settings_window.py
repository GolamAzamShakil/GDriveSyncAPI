"""
Tkinter schedule-settings window.
"""
from __future__ import annotations

import threading
import tkinter as tk
import tkinter.messagebox as mb

from core.config import APP_NAME
from core.schedule import SCHEDULE, _valid_hhmm
from core.state import request_force_poll

_settings_open = threading.Event()


def open_settings_window(tray_icon=None) -> None:
    if _settings_open.is_set():
        return
    _settings_open.set()

    def build():
        win = tk.Tk()
        win.title(f"{APP_NAME} — Schedule Settings")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        BG       = "#1e1e2e"; PANEL = "#2a2a3e"; ACCENT = "#4f9ef8"
        TEXT     = "#e0e0f0"; SUBTEXT = "#9090b0"; ENTRY_BG = "#12121e"

        win.configure(bg=BG)
        W, H = 480, 470
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        tk.Frame(win, bg=ACCENT, height=4).pack(fill="x")
        tk.Label(win, text="⚙  Polling Schedule",
                 font=("Segoe UI Semibold", 13), bg=BG, fg=TEXT
                 ).pack(pady=(14, 4))

        ie, isec, ce, ctimes = SCHEDULE.get()
        ih, im = divmod(isec // 60, 60)

        int_frame = tk.LabelFrame(win, text="  Interval Mode  ",
                                  bg=PANEL, fg=ACCENT, font=("Segoe UI", 9),
                                  bd=1, relief="groove")
        int_frame.pack(fill="x", padx=20, pady=(8, 4))

        int_var = tk.BooleanVar(value=ie)
        tk.Checkbutton(int_frame, text="Enable interval polling",
                       variable=int_var, bg=PANEL, fg=TEXT,
                       selectcolor=ENTRY_BG, activebackground=PANEL,
                       font=("Segoe UI", 9)
                       ).grid(row=0, column=0, columnspan=5,
                              sticky="w", padx=8, pady=(6, 2))
        tk.Label(int_frame, text="Every", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=1, column=0, padx=(8, 2), pady=4)

        h_var = tk.StringVar(value=str(ih))
        m_var = tk.StringVar(value=str(im))
        tk.Entry(int_frame, textvariable=h_var, width=4,
                 bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Consolas", 10)
                 ).grid(row=1, column=1, padx=2)
        tk.Label(int_frame, text="h", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=1, column=2)
        tk.Entry(int_frame, textvariable=m_var, width=4,
                 bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Consolas", 10)
                 ).grid(row=1, column=3, padx=2)
        tk.Label(int_frame, text="min", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=1, column=4, padx=(0, 8))

        clk_frame = tk.LabelFrame(win, text="  Clock Mode  ",
                                  bg=PANEL, fg=ACCENT, font=("Segoe UI", 9),
                                  bd=1, relief="groove")
        clk_frame.pack(fill="x", padx=20, pady=4)

        clk_var = tk.BooleanVar(value=ce)
        tk.Checkbutton(clk_frame, text="Enable clock-based polling",
                       variable=clk_var, bg=PANEL, fg=TEXT,
                       selectcolor=ENTRY_BG, activebackground=PANEL,
                       font=("Segoe UI", 9)
                       ).pack(anchor="w", padx=8, pady=(6, 2))
        tk.Label(clk_frame, text="Times (HH:MM, comma-separated, 24h):",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)
                 ).pack(anchor="w", padx=8)
        times_var = tk.StringVar(value=", ".join(ctimes))
        tk.Entry(clk_frame, textvariable=times_var, width=38,
                 bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Consolas", 10)
                 ).pack(padx=8, pady=(2, 8), fill="x")

        status_var = tk.StringVar(value=SCHEDULE.countdown_label())
        tk.Label(win, textvariable=status_var,
                 font=("Segoe UI", 8), bg=BG, fg=SUBTEXT).pack(pady=(6, 0))
        err_var = tk.StringVar()
        tk.Label(win, textvariable=err_var,
                 font=("Segoe UI", 8), bg=BG, fg="#ff6060").pack()

        def apply():
            errors = []
            try:
                hv = int(h_var.get()); mv = int(m_var.get())
                if hv < 0 or mv < 0 or mv > 59: raise ValueError
                secs = hv * 3600 + mv * 60
                if secs < 60: errors.append("Interval must be ≥ 1 minute.")
            except ValueError:
                errors.append("Invalid interval hours/minutes.")
                secs = 0
            raw    = times_var.get()
            parsed = [t.strip() for t in raw.split(",") if t.strip()]
            bad    = [t for t in parsed if not _valid_hhmm(t)]
            if bad: errors.append(f"Invalid time(s): {', '.join(bad)}")
            if errors: err_var.set("\n".join(errors)); return
            err_var.set("")
            SCHEDULE.set_interval(int_var.get(), secs)
            SCHEDULE.set_clock(clk_var.get(), parsed)
            status_var.set(SCHEDULE.countdown_label())

        def scan_now():
            apply()
            request_force_poll()
            mb.showinfo("Scan Now", "Scan queued — starts within 30 s.", parent=win)

        bf = tk.Frame(win, bg=BG); bf.pack(pady=14)
        for txt, cmd, color in [
            ("Apply",    apply,       ACCENT),
            ("Scan Now", scan_now,    "#3a9a50"),
            ("Close",    win.destroy, "#555577"),
        ]:
            tk.Button(bf, text=txt, command=cmd,
                      bg=color, fg=TEXT, relief="flat",
                      font=("Segoe UI Semibold", 9),
                      padx=14, pady=6, cursor="hand2",
                      activebackground=color
                      ).pack(side="left", padx=6)

        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.mainloop()
        _settings_open.clear()

    threading.Thread(target=build, daemon=True).start()
