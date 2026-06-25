import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import threading
import queue
import ctypes
import time
import os
import re
import ast
import webbrowser
from ctypes import c_int, c_void_p, Structure, sizeof, windll, pointer, byref
from ctypes import wintypes
from modules.i18n import T, get_language

def _fix_window_rendering(widget):
    """Strip WS_EX_LAYERED after the window is fully shown via after().
    Without this, overrideredirect windows appear black/invisible in screenshots on some GPU drivers.
    Uses after() so it runs after widgets are drawn, not during init (which caused gray blank windows).
    """
    def _do_fix():
        try:
            GWL_EXSTYLE   = -20
            WS_EX_LAYERED = 0x00080000
            hwnd = widget.winfo_id()
            if hwnd:
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if style & WS_EX_LAYERED:
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        except Exception:
            pass
    widget.after(100, _do_fix)

# ── Flask Dashboard ────────────────────────────────────────────────────────────
FLASK_PORT = 5000
FLASK_URL  = f"http://127.0.0.1:{FLASK_PORT}"
_flask_started = False

def start_flask_dashboard():
    """Launch the Flask web dashboard in a background daemon thread."""
    global _flask_started
    if _flask_started:
        return
    _flask_started = True

    def _run():
        try:
            import sys
            _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, _base)
            from app import app as flask_app
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)  # suppress Flask request logs
            flask_app.run(host="127.0.0.1", port=FLASK_PORT, debug=False, use_reloader=False)
        except Exception as e:
            print(f"[Dashboard] Flask error: {e}")

    t = threading.Thread(target=_run, name="FlaskDashboard", daemon=True)
    t.start()
    # Give Flask a moment to bind
    time.sleep(1.2)
    print(f"[Dashboard] Web UI running at {FLASK_URL}")

def open_dashboard_in_browser():
    """Open the dashboard in the user's default browser (not necessarily Chrome)."""
    try:
        # webbrowser.open uses the OS default browser, not the Selenium Chrome
        webbrowser.open(FLASK_URL, new=2)  # new=2 → open in new tab if possible
    except Exception as e:
        print(f"[Dashboard] Could not open browser: {e}")

# Enable DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Thread-safe queues
status_queue = queue.Queue()
action_queue = queue.Queue()
alert_queue = queue.Queue()

# UI State variables — shared between UI thread and bot thread
is_paused = False
is_stopped = False
career_ops_mode = False
active_driver = None
current_ui_status = "Status: Idle"
current_ui_details = ""
current_ui_action = ""

# API usage tracking — updated from AI provider modules
_api_tokens_used = 0
_api_token_budget = 100000  # default session budget; adjust if needed

def update_api_usage(tokens: int) -> None:
    global _api_tokens_used
    _api_tokens_used += tokens

# Windows API structures for DWM Blur/Acrylic
class AccentPolicy(Structure):
    _fields_ = [
        ("AccentState", c_int),
        ("AccentFlags", c_int),
        ("GradientColor", c_int),
        ("AnimationId", c_int)
    ]

class WindowCompositionAttributeData(Structure):
    _fields_ = [
        ("Attribute", c_int),
        ("Data", c_void_p),
        ("SizeOfData", c_int)
    ]

def enable_acrylic_blur(hwnd, color_abgr=0x88080808):
    # Acrylic blur (ACCENT_ENABLE_ACRYLICBLURBEHIND) places the window in a
    # separate DWM composition surface. On some GPU drivers this causes widgets
    # to appear gray/blank on-screen while still showing in DWM-based captures.
    # Disabled to ensure consistent rendering across all hardware.
    pass

def get_dpi_scaling():
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0

# Hotkey listener thread
def hotkey_listener_thread():
    user32 = ctypes.windll.user32
    msg = wintypes.MSG()
    user32.PeekMessageW(byref(msg), None, 0, 0, 0)
    STOP_ID_Q = 101
    STOP_ID_C = 103
    PAUSE_ID = 102
    MOD_CTRL = 0x0002
    MOD_SHIFT = 0x0004
    if not user32.RegisterHotKey(None, STOP_ID_Q, MOD_CTRL | MOD_SHIFT, 0x51):
        print("[BotUI] Failed to register Stop (Q) hotkey")
    if not user32.RegisterHotKey(None, STOP_ID_C, MOD_CTRL | MOD_SHIFT, 0x43):
        print("[BotUI] Failed to register Stop (C) hotkey")
    if not user32.RegisterHotKey(None, PAUSE_ID, MOD_CTRL | MOD_SHIFT, 0x50):
        print("[BotUI] Failed to register Pause hotkey")
    try:
        while user32.GetMessageW(byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:
                if msg.wParam in [STOP_ID_Q, STOP_ID_C]:
                    print("[BotUI] Hotkey STOP triggered. Force-exiting...")
                    def _hotkey_kill():
                        def _force():
                            time.sleep(5)
                            os._exit(0)
                        threading.Thread(target=_force, daemon=True).start()
                        try:
                            if active_driver:
                                active_driver.quit()
                        except Exception:
                            pass
                        os._exit(0)
                    threading.Thread(target=_hotkey_kill, daemon=True).start()
                elif msg.wParam == PAUSE_ID:
                    global is_paused
                    is_paused = not is_paused
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))
    finally:
        user32.UnregisterHotKey(None, STOP_ID_Q)
        user32.UnregisterHotKey(None, STOP_ID_C)
        user32.UnregisterHotKey(None, PAUSE_ID)


# Draggable Window Logic
class DragManager:
    def __init__(self, root):
        self.root = root
        root.bind("<Button-1>", self.start_move)
        root.bind("<ButtonRelease-1>", self.stop_move)
        root.bind("<B1-Motion>", self.on_move)
        self.x = 0
        self.y = 0

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def on_move(self, event):
        if self.x is not None and self.y is not None:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

# Resizable Window Logic
class ResizeManager:
    def __init__(self, root, grip_widget, min_w=300, min_h=140):
        self.root = root
        self.grip = grip_widget
        self.min_w = min_w
        self.min_h = min_h
        self.grip.bind("<Button-1>", self.start_resize)
        self.grip.bind("<B1-Motion>", self.on_resize)
        self.start_x = 0
        self.start_y = 0
        self.start_w = 0
        self.start_h = 0

    def start_resize(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_w = self.root.winfo_width()
        self.start_h = self.root.winfo_height()

    def on_resize(self, event):
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        new_w = max(self.min_w, self.start_w + dx)
        new_h = max(self.min_h, self.start_h + dy)
        self.root.geometry(f"{new_w}x{new_h}")


# Custom glassmorphism alert window
class GlassAlert(tk.Toplevel):
    def __init__(self, parent, title, message, response_queue, btn_label=None):
        super().__init__(parent)
        self.response_queue = response_queue
        scaling = get_dpi_scaling()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        _fix_window_rendering(self)
        self.configure(bg="#050505")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        # Auto-size height based on how many lines the message has
        line_count = len(message.split("\n"))
        base_h = 200
        extra = max(0, line_count - 4) * 18
        w, h = int(420 * scaling), int((base_h + extra) * scaling)
        h = min(h, int(sh * 0.8))   # never exceed 80% of screen height

        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.drag = DragManager(self)
        self.update()
        hwnd = windll.user32.GetParent(self.winfo_id())
        enable_acrylic_blur(hwnd, 0x88080808)
        frame = tk.Frame(self, bg="#0a0a0c", bd=1, highlightbackground="#333339", highlightcolor="#333339", highlightthickness=1)
        frame.place(x=1, y=1, width=w-2, height=h-2)
        title_label = tk.Label(frame, text=title.upper(), fg="#7F5AF0", bg="#0a0a0c", font=("Segoe UI Semibold", 10), anchor="w")
        title_label.pack(fill="x", padx=15, pady=(15, 5))
        msg_label = tk.Label(frame, text=message, fg="#E6E6E8", bg="#0a0a0c", font=("Segoe UI", 9), justify="left", wraplength=int(390 * scaling), anchor="nw")
        msg_label.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        btn_frame = tk.Frame(frame, bg="#0a0a0c")
        btn_frame.pack(fill="x", side="bottom", pady=(8, 14))
        label = btn_label or T("btn_resume")
        btn = tk.Button(btn_frame, text=label.upper(), fg="#FFFFFE", bg="#7F5AF0", activeforeground="#FFFFFE", activebackground="#9270F2", bd=0, padx=24, pady=8, font=("Segoe UI Bold", 9), command=self.on_continue, cursor="hand2")
        btn.pack(anchor="center")
        self.bell()

    def on_continue(self):
        self.response_queue.put(True)
        self.destroy()


# Custom glassmorphism confirm window
class GlassConfirm(tk.Toplevel):
    def __init__(self, parent, title, message, buttons, response_queue):
        super().__init__(parent)
        self.response_queue = response_queue
        scaling = get_dpi_scaling()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        _fix_window_rendering(self)
        self.configure(bg="#050505")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        line_count = len(message.split("\n"))
        base_h = 210
        extra = max(0, line_count - 5) * 18
        w, h = int(490 * scaling), int((base_h + extra) * scaling)
        h = min(h, int(sh * 0.8))

        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.drag = DragManager(self)
        self.update()
        hwnd = windll.user32.GetParent(self.winfo_id())
        enable_acrylic_blur(hwnd, 0x88080808)
        frame = tk.Frame(self, bg="#0a0a0c", bd=1, highlightbackground="#333339", highlightcolor="#333339", highlightthickness=1)
        frame.place(x=1, y=1, width=w-2, height=h-2)
        title_label = tk.Label(frame, text=title.upper(), fg="#7F5AF0", bg="#0a0a0c", font=("Segoe UI Semibold", 10), anchor="w")
        title_label.pack(fill="x", padx=15, pady=(15, 5))
        msg_label = tk.Label(frame, text=message, fg="#E6E6E8", bg="#0a0a0c", font=("Segoe UI", 9), justify="left", wraplength=int(460 * scaling), anchor="nw")
        msg_label.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        btn_frame = tk.Frame(frame, bg="#0a0a0c")
        btn_frame.pack(fill="x", side="bottom", padx=10, pady=(8, 14))
        for idx, btn_text in enumerate(buttons):
            is_accent = (idx == len(buttons) - 1)
            bg_color = "#7F5AF0" if is_accent else "#2D2D30"
            active_bg = "#9270F2" if is_accent else "#3A3A3F"
            btn = tk.Button(btn_frame, text=btn_text.upper(), fg="#FFFFFE", bg=bg_color, activeforeground="#FFFFFE", activebackground=active_bg, bd=0, padx=14, pady=7, font=("Segoe UI Bold", 8), command=lambda val=btn_text: self.on_click(val), cursor="hand2")
            btn.pack(side="right", padx=6)
        self.bell()

    def on_click(self, value):
        self.response_queue.put(value)
        self.destroy()


# Simple text-input dialog used by CV wizard for missing fields
class GlassAskText(tk.Toplevel):
    def __init__(self, parent, title, question, placeholder, response_queue):
        super().__init__(parent)
        self.response_queue = response_queue
        scaling = get_dpi_scaling()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        _fix_window_rendering(self)
        self.configure(bg="#050505")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(440 * scaling), int(200 * scaling)
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.drag = DragManager(self)
        frame = tk.Frame(self, bg="#0a0a0c", bd=1, highlightbackground="#333339", highlightthickness=1)
        frame.place(x=1, y=1, width=w-2, height=h-2)
        tk.Label(frame, text=title.upper(), fg="#7F5AF0", bg="#0a0a0c",
                 font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x", padx=15, pady=(14, 2))
        tk.Label(frame, text=question, fg="#E6E6E8", bg="#0a0a0c",
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=15, pady=(2, 6))
        self._var = tk.StringVar(value=placeholder)
        entry = tk.Entry(frame, textvariable=self._var, fg="#E6E6E8", bg="#1a1a1f",
                         insertbackground="#E6E6E8", bd=0, font=("Segoe UI", 10),
                         highlightbackground="#444", highlightthickness=1)
        entry.pack(fill="x", padx=15, ipady=6)
        entry.focus_set()
        entry.select_range(0, "end")
        btn_f = tk.Frame(frame, bg="#0a0a0c")
        btn_f.pack(fill="x", side="bottom", pady=12)
        tk.Button(btn_f, text="SALTAR", fg="#888", bg="#0a0a0c", bd=0,
                  font=("Segoe UI", 9), command=self._skip, cursor="hand2").pack(side="left", padx=20)
        tk.Button(btn_f, text="GUARDAR", fg="#FFFFFE", bg="#7F5AF0", activebackground="#9270F2",
                  bd=0, padx=20, pady=6, font=("Segoe UI Bold", 9),
                  command=self._save, cursor="hand2").pack(side="right", padx=20)
        self.bind("<Return>", lambda e: self._save())
        self.bell()

    def _save(self):
        self.response_queue.put(self._var.get().strip())
        self.destroy()

    def _skip(self):
        self.response_queue.put("")
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS PANEL
# ─────────────────────────────────────────────────────────────────────────────

def _read_py_var(filepath, varname):
    """Read a variable value from a Python config file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == varname:
                        try:
                            return ast.literal_eval(node.value)
                        except Exception:
                            # Return raw source slice for complex expressions
                            return ast.get_source_segment(source, node.value)
    except Exception as e:
        print(f"[Settings] Error reading {varname} from {filepath}: {e}")
    return None

def _write_py_var(filepath, varname, new_value):
    """Overwrite a variable assignment in a Python config file using ast line ranges."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        lines = source.splitlines(keepends=True)

        # Format the new value as Python source
        if isinstance(new_value, str):
            if "\n" in new_value:
                replacement = f'{varname} = """\n{new_value}\n"""'
            else:
                escaped = new_value.replace("\\", "\\\\").replace('"', '\\"')
                replacement = f'{varname} = "{escaped}"'
        elif isinstance(new_value, bool):
            replacement = f'{varname} = {new_value}'
        elif isinstance(new_value, (int, float)):
            replacement = f'{varname} = {new_value}'
        elif isinstance(new_value, list):
            if new_value:
                items = ",\n    ".join(repr(v) for v in new_value)
                replacement = f'{varname} = [\n    {items}\n]'
            else:
                replacement = f'{varname} = []'
        else:
            replacement = f'{varname} = {repr(new_value)}'

        # Use ast to find the exact line range of the assignment
        try:
            tree = ast.parse(source)
            found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == varname:
                            # ast lines are 1-indexed
                            start_line = node.col_offset  # unused but kept for clarity
                            first = node.lineno - 1       # 0-indexed
                            last = node.end_lineno - 1    # 0-indexed, inclusive
                            new_lines = lines[:first] + [replacement + "\n"] + lines[last + 1:]
                            new_source = "".join(new_lines)
                            found = True
                            break
                if found:
                    break

            if not found:
                new_source = source.rstrip() + f"\n{replacement}\n"

        except Exception:
            # Fallback: simple single-line regex replacement (safe for simple vars)
            pattern = rf'^{re.escape(varname)}\s*=\s*[^\n]+'
            new_source = re.sub(pattern, replacement, source, count=1, flags=re.MULTILINE)
            if new_source == source:
                new_source = source.rstrip() + f"\n{replacement}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_source)
        return True
    except Exception as e:
        print(f"[Settings] Error writing {varname} to {filepath}: {e}")
        return False




BG = "#0a0a0c"
BG2 = "#131316"
FG = "#E6E6E8"
FG_DIM = "#94A1B2"
ACCENT = "#7F5AF0"
ACCENT2 = "#00E8C6"
BORDER = "#2d2d30"

def _styled_label(parent, text, small=False):
    size = 8 if small else 9
    return tk.Label(parent, text=text, fg=FG_DIM, bg=BG2, font=("Segoe UI", size))

def _styled_entry(parent, width=38):
    e = tk.Entry(parent, bg=BG, fg=FG, insertbackground=FG, font=("Consolas", 9),
                 bd=0, highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT, width=width, relief="flat")
    return e

def _styled_text(parent, height=4, width=38):
    t = tk.Text(parent, bg=BG, fg=FG, insertbackground=FG, font=("Consolas", 9),
                bd=0, highlightthickness=1, highlightbackground=BORDER,
                highlightcolor=ACCENT, height=height, width=width, relief="flat",
                wrap="word")
    return t

def _styled_check(parent, text, var):
    return tk.Checkbutton(parent, text=text, variable=var,
                          fg=FG, bg=BG2, selectcolor=BG,
                          activeforeground=FG, activebackground=BG2,
                          font=("Segoe UI", 9), anchor="w")

def _section_title(parent, text):
    tk.Label(parent, text=text, fg=ACCENT, bg=BG2,
             font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=12, pady=(10, 2))
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(0, 6))


class GlassSettings(tk.Toplevel):
    """Settings panel opened via the ⚙ gear button."""

    # Config file paths (relative to project root, resolved at runtime)
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SEARCH  = os.path.join(_BASE, "config", "search.py")
    _PERS    = os.path.join(_BASE, "config", "personals.py")
    _QUEST   = os.path.join(_BASE, "config", "questions.py")
    _SETT    = os.path.join(_BASE, "config", "settings.py")
    _SECR    = os.path.join(_BASE, "config", "secrets.py")

    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        _fix_window_rendering(self)
        self.configure(bg="#050505")
        self.resizable(True, True)

        scaling = get_dpi_scaling()
        w, h = int(580 * scaling), int(600 * scaling)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.update()
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            enable_acrylic_blur(hwnd, 0xCC0a0a0c)
        except Exception:
            pass

        # Outer border frame
        outer = tk.Frame(self, bg=BG, bd=0, highlightbackground=BORDER,
                         highlightcolor=BORDER, highlightthickness=1)
        outer.place(x=1, y=1, relwidth=1, relheight=1, width=-2, height=-2)

        # Header bar
        hdr = tk.Frame(outer, bg=BG, height=36)
        hdr.pack(fill="x", padx=0)
        hdr.pack_propagate(False)

        tk.Label(hdr, text=f"  {T('cfg_title')}", fg=ACCENT, bg=BG,
                 font=("Segoe UI Bold", 10)).pack(side="left", padx=8)

        close_lbl = tk.Label(hdr, text="  X  ", fg=FG_DIM, bg=BG,
                             font=("Segoe UI Bold", 10), cursor="hand2")
        close_lbl.pack(side="right", padx=4)
        close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg="#E74C3C"))
        close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg=FG_DIM))
        close_lbl.bind("<Button-1>", lambda e: self.destroy())

        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x")

        # Tab notebook (custom styled)
        self._tab_btns = {}
        self._tab_frames = {}
        self._active_tab = tk.StringVar(value="search")

        tab_bar = tk.Frame(outer, bg=BG, height=32)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        tabs = [(T('cfg_tab_search'), "search"),
                (T('cfg_tab_personal'), "personal"),
                (T('cfg_tab_responses'), "responses"),
                (T('cfg_tab_bot'), "bot")]
        for label, key in tabs:
            btn = tk.Label(tab_bar, text=label, fg=FG_DIM, bg=BG,
                           font=("Segoe UI", 9), cursor="hand2", padx=12)
            btn.pack(side="left", fill="y")
            btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=FG) if b.cget("fg") != ACCENT else None)
            btn.bind("<Leave>", lambda e, b=btn, k=key: b.config(fg=FG_DIM) if self._active_tab.get() != k else None)
            self._tab_btns[key] = btn

        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x")

        # Content area
        self._content = tk.Frame(outer, bg=BG2)
        self._content.pack(fill="both", expand=True)

        # Save / Cancel bar
        btn_bar = tk.Frame(outer, bg=BG, height=44)
        btn_bar.pack(fill="x", side="bottom")
        btn_bar.pack_propagate(False)
        tk.Frame(btn_bar, bg=BORDER, height=1).pack(fill="x", side="top")

        tk.Button(btn_bar, text=T("cfg_cancel"), fg=FG_DIM, bg=BG,
                  activeforeground=FG, activebackground=BG2,
                  bd=0, padx=14, pady=5, font=("Segoe UI Bold", 8),
                  command=self.destroy, cursor="hand2").pack(side="right", padx=8, pady=7)

        tk.Button(btn_bar, text=f"  {T('cfg_save')}  ", fg="#101012", bg=ACCENT2,
                  activeforeground="#101012", activebackground="#00c9aa",
                  bd=0, padx=14, pady=5, font=("Segoe UI Bold", 8),
                  command=self._save_all, cursor="hand2").pack(side="right", padx=4, pady=7)

        self._fields = {}   # key -> (type, widget)
        self._build_all_tabs()
        self._switch_tab("search")
        DragManager(self)

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _switch_tab(self, key):
        for k, fr in self._tab_frames.items():
            fr.pack_forget()
        for k, btn in self._tab_btns.items():
            btn.config(fg=FG_DIM, font=("Segoe UI", 9))
        self._tab_frames[key].pack(fill="both", expand=True)
        self._tab_btns[key].config(fg=ACCENT, font=("Segoe UI Semibold", 9))
        self._active_tab.set(key)

    # ── Scrollable frame helper ───────────────────────────────────────────────

    def _make_scroll_frame(self, parent):
        canvas = tk.Canvas(parent, bg=BG2, bd=0, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG2)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        def _on_mousewheel(event):
            w = event.widget
            while w:
                if isinstance(w, tk.Canvas):
                    w.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    break
                parent = w.winfo_parent()
                if not parent:
                    break
                try:
                    w = w.nametowidget(parent)
                except Exception:
                    break
                    
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        return inner

    # ── Row builders ─────────────────────────────────────────────────────────

    def _browse_file(self, entry_widget):
        file_path = filedialog.askopenfilename(
            title="Seleccionar CV (PDF)",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")]
        )
        if file_path:
            file_path = os.path.normpath(file_path)
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file_path)

    def _add_entry(self, parent, field_key, label_text, filepath, varname, width=36, browse=False):
        _styled_label(parent, label_text).pack(anchor="w", padx=14, pady=(6, 1))
        if browse:
            row = tk.Frame(parent, bg=BG2)
            row.pack(anchor="w", padx=14, pady=(0, 2), fill="x")
            e = _styled_entry(row, width=width - 8)
            e.pack(side="left", fill="x", expand=True)
            btn = tk.Button(row, text="EXAMINAR", fg="#FFFFFE", bg="#2D2D30",
                            activeforeground="#FFFFFE", activebackground="#3A3A3F",
                            bd=0, padx=8, pady=2, font=("Segoe UI Bold", 7),
                            command=lambda: self._browse_file(e), cursor="hand2")
            btn.pack(side="left", padx=(6, 0))
        else:
            e = _styled_entry(parent, width=width)
            e.pack(anchor="w", padx=14, pady=(0, 2))
            
        val = _read_py_var(filepath, varname)
        if val is not None:
            e.insert(0, str(val))
        self._fields[field_key] = ("entry", e, filepath, varname)

    def _add_text(self, parent, field_key, label_text, filepath, varname, height=4):
        _styled_label(parent, label_text).pack(anchor="w", padx=14, pady=(6, 1))
        t = _styled_text(parent, height=height)
        t.pack(anchor="w", padx=14, pady=(0, 2), fill="x")
        val = _read_py_var(filepath, varname)
        if val is not None:
            t.insert("1.0", str(val).strip())
        self._fields[field_key] = ("text", t, filepath, varname)

    def _add_list(self, parent, field_key, label_text, filepath, varname, height=3):
        _styled_label(parent, f"{label_text}  (una por línea)", small=True).pack(anchor="w", padx=14, pady=(6, 1))
        t = _styled_text(parent, height=height)
        t.pack(anchor="w", padx=14, pady=(0, 2), fill="x")
        val = _read_py_var(filepath, varname)
        if isinstance(val, list):
            t.insert("1.0", "\n".join(str(v) for v in val))
        elif val is not None:
            t.insert("1.0", str(val))
        self._fields[field_key] = ("list", t, filepath, varname)

    def _add_bool(self, parent, field_key, label_text, filepath, varname):
        var = tk.BooleanVar()
        val = _read_py_var(filepath, varname)
        if val is not None:
            var.set(bool(val))
        cb = _styled_check(parent, label_text, var)
        cb.pack(anchor="w", padx=14, pady=3)
        self._fields[field_key] = ("bool", var, filepath, varname)

    def _add_multicheck(self, parent, field_key, label_text, filepath, varname, options, cols=3):
        _styled_label(parent, label_text).pack(anchor="w", padx=14, pady=(6, 1))
        container = tk.Frame(parent, bg=BG2)
        container.pack(anchor="w", padx=14, pady=(2, 6), fill="x")
        current_val = _read_py_var(filepath, varname) or []
        if not isinstance(current_val, list):
            current_val = []
        check_vars = {}
        for i, opt in enumerate(options):
            var = tk.BooleanVar(value=(opt in current_val))
            cb = _styled_check(container, opt, var)
            cb.grid(row=i // cols, column=i % cols, sticky="w", padx=(0, 18), pady=1)
            check_vars[opt] = var
        self._fields[field_key] = ("multicheck", check_vars, filepath, varname)

    def _add_dropdown(self, parent, field_key, label_text, filepath, varname, options):
        _styled_label(parent, label_text).pack(anchor="w", padx=14, pady=(6, 1))
        var = tk.StringVar()
        val = _read_py_var(filepath, varname)
        current = str(val) if val is not None else (options[0] if options else "")
        if current not in options and options:
            options = [current] + options
        var.set(current)
        menu = tk.OptionMenu(parent, var, *options)
        menu.config(bg=BG, fg=FG, activebackground=ACCENT, activeforeground="#FFFFFE",
                    font=("Segoe UI", 9), bd=0, highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=ACCENT,
                    relief="flat", anchor="w", width=28)
        menu["menu"].config(bg=BG, fg=FG, activebackground=ACCENT,
                            activeforeground="#FFFFFE", font=("Segoe UI", 9),
                            bd=0, tearoff=0)
        menu.pack(anchor="w", padx=14, pady=(0, 4))
        self._fields[field_key] = ("dropdown", var, filepath, varname)

    # ── Build tabs ────────────────────────────────────────────────────────────

    def _build_all_tabs(self):
        for key in ["search", "personal", "responses", "bot"]:
            outer = tk.Frame(self._content, bg=BG2)
            inner = self._make_scroll_frame(outer)
            self._tab_frames[key] = outer
            getattr(self, f"_build_tab_{key}")(inner)

    def _build_tab_search(self, p):
        _section_title(p, T("cfg_sec_search_main"))
        self._add_list(p, "search_terms", "Términos de búsqueda (search_terms)", self._SEARCH, "search_terms", height=5)
        self._add_entry(p, "search_location", "Ubicación (search_location)", self._SEARCH, "search_location")

        _section_title(p, T("cfg_sec_relevance"))
        self._add_list(p, "primary_focus_keywords", "Palabras clave PRINCIPALES (Help Desk, Tech Support...)", self._SEARCH, "primary_focus_keywords", height=3)
        self._add_list(p, "secondary_focus_keywords", "Palabras clave SECUNDARIAS (solo Remote/Hybrid)", self._SEARCH, "secondary_focus_keywords", height=3)
        self._add_bool(p, "enable_job_focus_filter", "Activar filtro de relevancia (skip trabajos irrelevantes)", self._SEARCH, "enable_job_focus_filter")

        _section_title(p, T("cfg_sec_filters"))
        self._add_entry(p, "switch_number", "Cambiar búsqueda cada N aplicaciones", self._SEARCH, "switch_number", width=10)
        self._add_dropdown(p, "date_posted", "Fecha publicada", self._SEARCH, "date_posted",
                           ["Past week", "Past 24 hours", "Past month", "Any time"])
        self._add_dropdown(p, "sort_by", "Ordenar por", self._SEARCH, "sort_by",
                           ["Most recent", "Most relevant"])
        self._add_multicheck(p, "on_site", "Modalidad de trabajo", self._SEARCH, "on_site",
                             ["On-site", "Hybrid", "Remote"])
        self._add_multicheck(p, "experience_level", "Nivel de experiencia", self._SEARCH, "experience_level",
                             ["Internship", "Entry level", "Associate", "Mid-Senior level", "Director", "Executive"], cols=3)
        self._add_multicheck(p, "job_type", "Tipo de empleo", self._SEARCH, "job_type",
                             ["Full-time", "Part-time", "Contract", "Temporary", "Internship", "Volunteer"], cols=3)
        self._add_bool(p, "easy_apply_only", "Solo Easy Apply", self._SEARCH, "easy_apply_only")
        self._add_bool(p, "randomize_search_order", "Aleatorizar orden de búsqueda", self._SEARCH, "randomize_search_order")

        _section_title(p, T("cfg_sec_avoid"))
        self._add_list(p, "bad_words", "Palabras malas en descripción (bad_words)", self._SEARCH, "bad_words", height=3)
        self._add_list(p, "about_company_bad_words", "Palabras malas en empresa", self._SEARCH, "about_company_bad_words", height=2)
        self._add_entry(p, "current_experience", "Experiencia actual en años (-1 = ignorar)", self._SEARCH, "current_experience", width=10)

    def _build_tab_personal(self, p):
        _section_title(p, T("cfg_sec_personal"))
        self._add_entry(p, "first_name", "Nombre (first_name)", self._PERS, "first_name")
        self._add_entry(p, "middle_name", "Segundo nombre (middle_name)", self._PERS, "middle_name")
        self._add_entry(p, "last_name", "Apellido (last_name)", self._PERS, "last_name")
        self._add_entry(p, "phone_number", "Teléfono (phone_number)", self._PERS, "phone_number")
        self._add_entry(p, "current_city", "Ciudad actual (current_city)", self._PERS, "current_city")
        self._add_entry(p, "state", "Estado/Departamento (state)", self._PERS, "state")
        self._add_entry(p, "country", "País (country)", self._PERS, "country")
        self._add_entry(p, "zipcode", "Código postal (zipcode)", self._PERS, "zipcode")
        self._add_entry(p, "street", "Calle (street)", self._PERS, "street")
        self._add_entry(p, "university", "Institución educativa (university)", self._PERS, "university")
        self._add_dropdown(p, "degree", "Nivel de educación (degree)", self._PERS, "degree",
                           ["High School", "Associate's", "Bachelor's", "Master's", "Doctorate", "Other"])
        self._add_entry(p, "graduation_year", "Año de graduación (graduation_year)", self._PERS, "graduation_year", width=10)
        self._add_entry(p, "field_of_study", "Campo de estudio / Major (field_of_study)", self._PERS, "field_of_study")
        self._add_entry(p, "identification_number", "Número de identificación", self._PERS, "identification_number")

        _section_title(p, T("cfg_sec_eeo"))
        self._add_dropdown(p, "gender", "Género", self._PERS, "gender",
                           ["Decline to self identify", "Male", "Female", "Other", "Non-binary"])
        self._add_entry(p, "ethnicity", "Etnia", self._PERS, "ethnicity")
        self._add_dropdown(p, "disability_status", "Discapacidad", self._PERS, "disability_status",
                           ["No", "Yes", "Decline to self identify"])
        self._add_dropdown(p, "veteran_status", "Veterano", self._PERS, "veteran_status",
                           ["No", "I am not a protected veteran",
                            "I identify as one or more of the classifications of a protected veteran",
                            "Decline to self identify"])

    def _build_tab_responses(self, p):
        _section_title(p, T("cfg_sec_exp"))
        self._add_entry(p, "years_of_experience", "Años de experiencia a reportar", self._QUEST, "years_of_experience", width=10)
        self._add_entry(p, "desired_salary", "Salario deseado (número)", self._QUEST, "desired_salary", width=16)
        self._add_entry(p, "current_ctc", "CTC actual (número)", self._QUEST, "current_ctc", width=16)
        self._add_entry(p, "notice_period", "Período de aviso en días", self._QUEST, "notice_period", width=10)
        self._add_dropdown(p, "require_visa", "¿Requiere visa de trabajo?", self._QUEST, "require_visa",
                           ["No", "Yes"])
        self._add_entry(p, "recent_employer", "Empleador más reciente", self._QUEST, "recent_employer")
        self._add_entry(p, "confidence_level", "Nivel de confianza 1-10", self._QUEST, "confidence_level", width=10)
        self._add_entry(p, "us_citizenship", "Ciudadanía US", self._QUEST, "us_citizenship")

        _section_title(p, T("cfg_sec_links"))
        self._add_entry(p, "linkedIn", "URL de LinkedIn", self._QUEST, "linkedIn")
        self._add_entry(p, "website", "Portfolio / Website", self._QUEST, "website")

        _section_title(p, T("cfg_sec_texts"))
        self._add_entry(p, "linkedin_headline", "Titular de LinkedIn", self._QUEST, "linkedin_headline")
        self._add_text(p, "linkedin_summary", "Resumen de LinkedIn", self._QUEST, "linkedin_summary", height=5)
        self._add_text(p, "cover_letter", "Carta de presentación", self._QUEST, "cover_letter", height=8)
        self._add_text(p, "user_information_all", "Información completa para IA", self._QUEST, "user_information_all", height=8)
        self._add_entry(p, "default_resume_path", "Ruta del CV (PDF)", self._QUEST, "default_resume_path", browse=True)

    def _build_tab_bot(self, p):
        _section_title(p, T("cfg_sec_linkedin"))
        self._add_entry(p, "username", "Email de LinkedIn (usuario)", self._SECR, "username")
        self._add_entry(p, "password", "Contraseña de LinkedIn", self._SECR, "password")

        _section_title(p, T("cfg_sec_behavior"))
        self._add_bool(p, "pause_before_submit", "Pausar antes de enviar cada aplicación", self._QUEST, "pause_before_submit")
        self._add_bool(p, "pause_at_failed_question", "Pausar si no puede responder una pregunta", self._QUEST, "pause_at_failed_question")
        self._add_bool(p, "overwrite_previous_answers", "Sobreescribir respuestas anteriores", self._QUEST, "overwrite_previous_answers")
        self._add_bool(p, "run_non_stop", "Correr sin parar (run_non_stop)", self._SETT, "run_non_stop")
        self._add_bool(p, "follow_companies", "Seguir empresas al aplicar", self._SETT, "follow_companies")
        self._add_bool(p, "close_tabs", "Cerrar tabs de aplicaciones externas", self._SETT, "close_tabs")

        _section_title(p, T("cfg_sec_browser"))
        self._add_entry(p, "click_gap", "Pausa entre clicks (seg)", self._SETT, "click_gap", width=10)
        self._add_bool(p, "run_in_background", "Correr en fondo (sin Chrome visible)", self._SETT, "run_in_background")
        self._add_bool(p, "smooth_scroll", "Scroll suave", self._SETT, "smooth_scroll")
        self._add_bool(p, "stealth_mode", "Modo stealth (anti-bot)", self._SETT, "stealth_mode")
        self._add_bool(p, "safe_mode", "Modo seguro (perfil invitado)", self._SETT, "safe_mode")
        self._add_bool(p, "keep_screen_awake", "Mantener pantalla activa", self._SETT, "keep_screen_awake")

        _section_title(p, T("cfg_sec_cycles"))
        self._add_bool(p, "alternate_sortby", "Alternar orden de resultados", self._SETT, "alternate_sortby")
        self._add_bool(p, "cycle_date_posted", "Ciclar filtro de fecha automáticamente", self._SETT, "cycle_date_posted")
        self._add_bool(p, "stop_date_cycle_at_24hr", "Parar ciclo al llegar a 24h", self._SETT, "stop_date_cycle_at_24hr")

        _section_title(p, T("lang_label"))
        self._add_dropdown(p, "ui_language", T("lang_label"), self._SETT, "ui_language",
                           ["es", "en"])

        _section_title(p, T("cfg_sec_ai"))
        _styled_label(p, "Proveedor:  groq (gratis) | gemini | openai | deepseek", small=True).pack(anchor="w", padx=14, pady=(2, 1))
        self._add_entry(p, "ai_provider", "Proveedor de IA (ai_provider)", self._SECR, "ai_provider", width=16)
        self._add_entry(p, "llm_api_key", "API Key (groq.com → API Keys → Create key)", self._SECR, "llm_api_key", width=38)
        self._add_entry(p, "llm_model", "Modelo (llama-3.1-8b-instant para Groq)", self._SECR, "llm_model", width=30)
        self._add_entry(p, "llm_api_url", "URL de API (solo para openai/ollama)", self._SECR, "llm_api_url", width=38)
        self._add_bool(p, "use_AI", "Activar IA (use_AI)", self._SECR, "use_AI")

    # ── Save logic ────────────────────────────────────────────────────────────

    def _save_all(self):
        from modules.i18n import get_language
        _lang_before = get_language()
        errors = []
        for field_key, field_data in self._fields.items():
            ftype = field_data[0]
            widget = field_data[1]
            filepath = field_data[2]
            varname = field_data[3]
            try:
                if ftype == "entry":
                    raw = widget.get().strip()
                    numeric_fields = {'switch_number', 'current_experience', 'desired_salary', 'notice_period', 'current_ctc', 'click_gap'}
                    if varname in numeric_fields:
                        try:
                            val = ast.literal_eval(raw)
                        except Exception:
                            val = raw
                    else:
                        val = raw
                elif ftype == "text":
                    val = widget.get("1.0", "end-1c").strip()
                elif ftype == "list":
                    lines = [l.strip().strip("\"'") for l in widget.get("1.0", "end-1c").splitlines() if l.strip()]
                    val = lines
                elif ftype == "bool":
                    val = widget.get()
                elif ftype == "multicheck":
                    val = [opt for opt, bv in widget.items() if bv.get()]
                elif ftype == "dropdown":
                    val = widget.get()
                else:
                    continue

                ok = _write_py_var(filepath, varname, val)
                if not ok:
                    errors.append(f"{varname}")
            except Exception as e:
                errors.append(f"{varname}: {e}")

        if errors:
            self._show_result(f"[!] {T('cfg_saved_err')}{', '.join(errors)}", error=True)
        else:
            self._show_result(T('cfg_saved_ok'))
            # If language changed, rebuild the settings panel in the new language
            from modules.i18n import get_language, _lang_cache
            _lang_cache.clear()  # force re-read after write
            if get_language() != _lang_before:
                parent = self.master
                self.after(120, lambda: (self.destroy(), GlassSettings(parent)))

    def _show_result(self, msg, error=False):
        color = "#E74C3C" if error else ACCENT2
        lbl = tk.Label(self, text=msg, fg=color, bg=BG,
                       font=("Segoe UI", 9))
        lbl.place(relx=0.5, rely=0.96, anchor="center")
        self.after(3000, lbl.destroy)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN UI APP
# ─────────────────────────────────────────────────────────────────────────────

class BotUIApp:
    def __init__(self, root):
        self.root = root
        self.scaling = get_dpi_scaling()
        print("[BotUI] DPI Scaling Factor:", self.scaling)

        self.w = int(360 * self.scaling)
        self.h = int(220 * self.scaling)

        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        _fix_window_rendering(root)
        root.configure(bg="#050505")

        sw = root.winfo_screenwidth()
        self.x = sw - self.w - int(20 * self.scaling)
        self.y = int(50 * self.scaling)

        self.drag = DragManager(root)

        self.border_frame = tk.Frame(root, bg="#0a0a0c", bd=1,
                                     highlightbackground="#2d2d30",
                                     highlightcolor="#2d2d30",
                                     highlightthickness=1)
        self.border_frame.place(x=1, y=1, width=self.w - 2, height=self.h - 2)

        # Header / Drag zone
        self.header = tk.Frame(self.border_frame, bg="#0a0a0c")
        self.header.pack(fill="x", padx=12, pady=(10, 4))

        # Pulsing status dot
        self.dot_canvas = tk.Canvas(self.header, width=10, height=10,
                                    bg="#0a0a0c", highlightthickness=0)
        self.dot_canvas.pack(side="left", padx=(0, 8))
        self.status_dot = self.dot_canvas.create_oval(1, 1, 9, 9, fill="#2ECC71", width=0)

        self.title_label = tk.Label(self.header, text="CVSNIPER CONTROL",
                                    fg="#E6E6E8", bg="#0a0a0c",
                                    font=("Segoe UI Bold", 9))
        self.title_label.pack(side="left")

        # Close button
        self.close_btn = tk.Label(self.header, text="X", fg="#94A1B2",
                                  bg="#0a0a0c", font=("Segoe UI Bold", 10),
                                  cursor="hand2")
        self.close_btn.pack(side="right", padx=(8, 0))
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="#E74C3C"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg="#94A1B2"))
        self.close_btn.bind("<Button-1>", lambda e: self.trigger_stop())

        # Settings button
        self.gear_btn = tk.Label(self.header, text="CFG", fg="#4c4c52",
                                 bg="#0a0a0c", font=("Segoe UI", 8),
                                 cursor="hand2")
        self.gear_btn.pack(side="right", padx=(0, 4))
        self.gear_btn.bind("<Enter>", lambda e: self.gear_btn.config(fg=ACCENT))
        self.gear_btn.bind("<Leave>", lambda e: self.gear_btn.config(fg="#4c4c52"))
        self.gear_btn.bind("<Button-1>", lambda e: self._open_settings())

        # Drag indicator
        self.drag_lbl = tk.Label(self.header, text=":::", fg="#4c4c52",
                                 bg="#0a0a0c", font=("Segoe UI", 9))
        self.drag_lbl.pack(side="right")

        # API usage bar
        self.api_row = tk.Frame(self.border_frame, bg="#0a0a0c")
        self.api_row.pack(side="bottom", fill="x", padx=12, pady=(0, 1))

        self.api_lbl = tk.Label(self.api_row, text="API  0 tok", fg="#4c4c52",
                                bg="#0a0a0c", font=("Consolas", 7), anchor="w")
        self.api_lbl.pack(side="left")

        self.api_pct_lbl = tk.Label(self.api_row, text="0%", fg="#4c4c52",
                                    bg="#0a0a0c", font=("Consolas", 7), anchor="e")
        self.api_pct_lbl.pack(side="right")

        self.api_bar_bg = tk.Frame(self.border_frame, bg="#1a1a20", height=3)
        self.api_bar_bg.pack(side="bottom", fill="x", padx=12, pady=(0, 2))
        self.api_bar_bg.pack_propagate(False)

        self.api_bar_fill = tk.Frame(self.api_bar_bg, bg="#7F5AF0", height=3)
        self.api_bar_fill.place(x=0, y=0, relheight=1, width=0)

        # Buttons Container — row 1: Dashboard + Settings
        self.top_btn_frame = tk.Frame(self.border_frame, bg="#0a0a0c")
        self.top_btn_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 2))

        self.dashboard_btn = tk.Button(
            self.top_btn_frame, text="Dashboard",
            fg="#00E8C6", bg="#131316",
            activeforeground="#00E8C6", activebackground="#1a1a20",
            bd=0, padx=10, pady=3,
            font=("Segoe UI Bold", 8),
            command=self._open_dashboard,
            cursor="hand2"
        )
        self.dashboard_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Buttons Container — row 2: main action buttons
        self.btn_frame = tk.Frame(self.border_frame, bg="#0a0a0c")
        self.btn_frame.pack(side="bottom", fill="x", padx=12, pady=(4, 8))

        # Mini Console Log Panel
        self.console_frame = tk.Frame(self.border_frame, bg="#050507", bd=1,
                                      relief="solid",
                                      highlightbackground="#222225",
                                      highlightthickness=1)
        self.console_frame.pack(fill="both", expand=True, padx=12, pady=(2, 4))

        self.console_box = tk.Text(self.console_frame, bg="#050507", fg="#94A1B2",
                                   font=("Consolas", 8), bd=0,
                                   highlightthickness=0, state="disabled",
                                   wrap="word", cursor="xterm")
        self.console_box.pack(fill="both", expand=True, padx=6, pady=4)
        self.console_box.bind("<Button-1>", lambda e: self.console_box.focus_set())
        self.console_box.bind("<Control-c>", self._copy_console_selection)

        self.console_box.tag_configure("status", foreground="#7F5AF0")
        self.console_box.tag_configure("info", foreground="#94A1B2")
        self.console_box.tag_configure("action", foreground="#00FFCC")
        self.console_box.tag_configure("system", foreground="#FFFFFE")

        # Resize grip
        self.grip = tk.Label(self.border_frame, text="◢", fg="#4c4c52",
                             bg="#0a0a0c", font=("Segoe UI", 8),
                             cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        self.resizer = ResizeManager(root, self.grip,
                                     min_w=int(280 * self.scaling),
                                     min_h=int(180 * self.scaling))

        # Pause Button
        self.pause_btn = tk.Button(self.btn_frame, text=T("btn_pause"),
                                   fg="#FFFFFE", bg="#2D2D30",
                                   activeforeground="#FFFFFE",
                                   activebackground="#3A3A3F",
                                   bd=0, padx=10, pady=4,
                                   font=("Segoe UI Bold", 8),
                                   command=self.toggle_pause,
                                   cursor="hand2")
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Career-Ops Button
        self.career_ops_btn = tk.Button(self.btn_frame, text="CAREER-OPS",
                                        fg="#FFFFFE", bg="#2D2D30",
                                        activeforeground="#FFFFFE",
                                        activebackground="#3A3A3F",
                                        bd=0, padx=8, pady=4,
                                        font=("Segoe UI Bold", 8),
                                        command=self.toggle_career_ops,
                                        cursor="hand2")
        self.career_ops_btn.pack(side="left", fill="x", expand=True, padx=(4, 4))

        # Optimize CV Button
        self.optimize_btn = tk.Button(self.btn_frame, text=T("btn_optimize_cv"),
                                      fg="#FFFFFE", bg="#2D2D30",
                                      activeforeground="#FFFFFE",
                                      activebackground="#3A3A3F",
                                      bd=0, padx=8, pady=4,
                                      font=("Segoe UI Bold", 8),
                                      command=self._trigger_optimize_cv,
                                      cursor="hand2")
        self.optimize_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Stop Button
        self.stop_btn = tk.Button(self.btn_frame, text=T("btn_stop"),
                                  fg="#FFFFFE", bg="#E74C3C",
                                  activeforeground="#FFFFFE",
                                  activebackground="#C0392B",
                                  bd=0, padx=10, pady=4,
                                  font=("Segoe UI Bold", 8),
                                  command=self.trigger_stop,
                                  cursor="hand2")
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        root.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")
        root.deiconify()
        root.update()

        self.hwnd = windll.user32.GetParent(root.winfo_id())
        enable_acrylic_blur(self.hwnd, 0x55080808)

        self.last_log_content = {}
        self.last_pause_state = False
        self._settings_win = None
        self._stop_confirm = False
        self._current_lang = get_language()
        self.add_log("System", "CVSniper Control initialized.", "system")

        self.poll_updates()

    def _open_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        self._settings_win = GlassSettings(self.root)

    def _open_dashboard(self):
        """Open web dashboard in the system default browser."""
        open_dashboard_in_browser()
        # Flash button to confirm
        self.dashboard_btn.config(bg="#00E8C6", fg="#0a0a0c")
        self.root.after(600, lambda: self.dashboard_btn.config(bg="#131316", fg="#00E8C6"))
        self.add_log("System", f"Dashboard abierto: {FLASK_URL}", "action")

    def _trigger_optimize_cv(self):
        threading.Thread(target=self._optimize_cv_flow, daemon=True).start()

    def _optimize_cv_flow(self):
        _existing = T("cv_opt_btn_existing")
        _scratch  = T("cv_opt_btn_scratch")
        _yes      = T("cv_port_btn_yes")
        choice = ui_confirm(T("cv_opt_title"), T("cv_opt_question"), [_existing, _scratch])
        if not choice:
            return
        if choice == _existing:
            file_path = filedialog.askopenfilename(title=T("cv_select_old"), filetypes=[("Archivos PDF", "*.pdf")])
            if not file_path:
                return
            inc_port = ui_confirm(T("cv_port_title"), T("cv_port_question"), [T("cv_port_btn_yes"), T("cv_port_btn_no")])
            self.add_log("System", T("cv_log_optimizing"), "system")
            try:
                from modules.ai.openaiConnections import ai_optimize_existing_cv
                success = ai_optimize_existing_cv(file_path, include_portfolio=(inc_port == _yes))
            except Exception as ex:
                self.add_log("System", f"Exception: {ex}", "status")
                success = False
            if success:
                self.add_log("System", T("cv_log_saved_opt"), "status")
                ui_alert(T("cv_success_title"), T("cv_success_opt"))
            else:
                self.add_log("System", T("cv_log_err_opt"), "status")
        elif choice == _scratch:
            inc_port = ui_confirm(T("cv_port_title"), T("cv_port_question"), [T("cv_port_btn_yes"), T("cv_port_btn_no")])
            self.add_log("System", T("cv_log_generating"), "system")
            try:
                from modules.ai.openaiConnections import ai_generate_cv_from_config
                success = ai_generate_cv_from_config(include_portfolio=(inc_port == _yes))
            except Exception as ex:
                self.add_log("System", f"Exception: {ex}", "status")
                success = False
            if success:
                self.add_log("System", T("cv_log_saved_gen"), "status")
                ui_alert(T("cv_success_title"), T("cv_success_gen"))
            else:
                self.add_log("System", T("cv_log_err_gen"), "status")

    def toggle_pause(self):
        global is_paused
        is_paused = not is_paused

    def toggle_career_ops(self):
        global career_ops_mode
        career_ops_mode = not career_ops_mode
        if career_ops_mode:
            self.career_ops_btn.config(bg="#7F5AF0", fg="#FFFFFE", activebackground="#9270F2")
            self.title_label.config(text="CVSNIPER - CAREER-OPS", fg="#00E8C6")
            self.add_log("System", "Modo Career-Ops activado. Se omitirá Easy Apply; todos los matches se abrirán manualmente.", "system")
            alert_msg = (
                "El Modo Career-Ops está activo:\n\n"
                "- Omitiendo postulaciones automáticas (Easy Apply).\n"
                "- Buscando y evaluando todas las vacantes usando IA.\n"
                "- Al encontrar 5 coincidencias, te preguntará si deseas abrirlas para postular manualmente.\n"
                "- Podrás confirmar si ya aplicaste para continuar con el siguiente ciclo."
            )
            GlassAlert(self.root, "Modo Career-Ops", alert_msg, queue.Queue())
        else:
            self.career_ops_btn.config(bg="#2D2D30", fg="#FFFFFE", activebackground="#3A3A3F")
            self.title_label.config(text="CVSNIPER CONTROL", fg="#E6E6E8")
            self.add_log("System", "Modo Career-Ops desactivado. LinkedIn Easy Apply estándar activo.", "system")

    def trigger_stop(self):
        if not self._stop_confirm:
            self._stop_confirm = True
            self.stop_btn.config(text=T("btn_confirm"), bg="#FF6B35")
            self.add_log("System", T("msg_confirm_stop"), "system")
            self.root.after(3000, self._reset_stop_btn)
            return
        self.add_log("System", T("msg_stopping"), "system")
        self.stop_btn.config(text=T("btn_stopping"), bg="#8B0000", state="disabled")
        self.dot_canvas.itemconfig(self.status_dot, fill="#E74C3C")
        self.root.update()

        def _kill():
            # Safety net: force-exit after 5s even if driver.quit() hangs
            def _force():
                time.sleep(5)
                os._exit(0)
            threading.Thread(target=_force, daemon=True).start()
            try:
                if active_driver:
                    active_driver.quit()
            except Exception:
                pass
            os._exit(0)

        threading.Thread(target=_kill, daemon=True).start()

    def _reset_stop_btn(self):
        if self._stop_confirm:
            self._stop_confirm = False
            self.stop_btn.config(text=T("btn_stop"), bg="#E74C3C")

    def add_log(self, prefix, text, tag="info"):
        if not text:
            return
        if self.last_log_content.get(prefix) == text:
            return
        self.last_log_content[prefix] = text
        self.console_box.configure(state="normal")
        self.console_box.insert("end", f"> {prefix.upper()}: ", tag)
        self.console_box.insert("end", f"{text}\n", "system" if tag == "action" else "info")
        num_lines = int(self.console_box.index('end-1c').split('.')[0])
        if num_lines > 100:
            self.console_box.delete("1.0", f"{num_lines - 100}.0")
        self.console_box.see("end")
        self.console_box.configure(state="disabled")

    def _copy_console_selection(self, event=None):
        try:
            selected = self.console_box.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass
        return "break"

    def _refresh_ui_texts(self):
        """Refresh all main-window widget texts when language changes."""
        self.optimize_btn.config(text=T("btn_optimize_cv"))
        if not self._stop_confirm and self.stop_btn.cget("state") != "disabled":
            self.stop_btn.config(text=T("btn_stop"))
        if not career_ops_mode:
            self.career_ops_btn.config(text=T("btn_career_ops"))

    def poll_updates(self):
        global is_paused, is_stopped, current_ui_status, current_ui_details, current_ui_action

        # 1. Process status queue
        while not status_queue.empty():
            msg_type, content = status_queue.get()
            if msg_type == "status":
                current_ui_status = content
                self.add_log("Status", content, "status")
            elif msg_type == "details":
                current_ui_details = content
                self.add_log("Info", content, "info")
            elif msg_type == "action":
                current_ui_action = content
                self.add_log("Action", content, "action")

        # 2. Process alert / confirm requests
        while not alert_queue.empty():
            item = alert_queue.get()
            self.dot_canvas.itemconfig(self.status_dot, fill="#F1C40F")
            if item[0] == "__ask_text__":
                _, title, question, placeholder, resp_q = item
                self.add_log("Setup", question, "status")
                GlassAskText(self.root, title, question, placeholder, resp_q)
            elif len(item) == 4:
                title, message, resp_q, buttons = item
                self.add_log("Alert", f"Action required: {title}", "status")
                GlassConfirm(self.root, title, message, buttons, resp_q)
            else:
                title, message, resp_q = item
                self.add_log("Alert", f"Action required: {title}", "status")
                GlassAlert(self.root, title, message, resp_q)

        # 3. Process pending actions from the action_queue
        while not action_queue.empty():
            act = action_queue.get()
            if isinstance(act, tuple) and act[0] == "open_settings":
                self._open_settings()
            elif act == "open_settings":
                self._open_settings()
            elif act == "pause":
                is_paused = not is_paused
            elif act == "stop":
                is_stopped = True

        # 4. Detect language change and refresh all widget texts
        _lang_now = get_language()
        if _lang_now != self._current_lang:
            self._current_lang = _lang_now
            self._refresh_ui_texts()

        # 5. Handle pause/resume state updates visually
        if is_paused != self.last_pause_state:
            self.last_pause_state = is_paused
            if is_paused:
                self.add_log("System", T("log_paused"), "system")
            else:
                self.add_log("System", T("log_resumed"), "system")

        if is_paused:
            self.pause_btn.config(text=T("btn_resume"), bg="#00E8C6", fg="#101012",
                                  activebackground="#00C9AA")
            self.dot_canvas.itemconfig(self.status_dot, fill="#F1C40F")
        else:
            self.pause_btn.config(text=T("btn_pause"), bg="#2D2D30", fg="#FFFFFE",
                                  activebackground="#3A3A3F")
            if is_stopped:
                self.dot_canvas.itemconfig(self.status_dot, fill="#E74C3C")
            else:
                self.dot_canvas.itemconfig(self.status_dot, fill="#2ECC71")

        # Update API usage bar
        try:
            used = _api_tokens_used
            budget = _api_token_budget
            pct = min(100, int(used / budget * 100)) if budget > 0 else 0
            bar_color = "#E74C3C" if pct >= 90 else "#F1C40F" if pct >= 70 else "#7F5AF0"
            used_str = f"{used:,}" if used < 1_000_000 else f"{used/1000:.1f}k"
            self.api_lbl.config(text=f"API  {used_str} tok", fg="#4c4c52" if pct < 70 else bar_color)
            self.api_pct_lbl.config(text=f"{pct}%", fg=bar_color if pct > 0 else "#4c4c52")
            bar_total = self.api_bar_bg.winfo_width()
            if bar_total > 1:
                self.api_bar_fill.place(x=0, y=0, relheight=1, width=int(bar_total * pct / 100))
                self.api_bar_fill.config(bg=bar_color)
        except Exception:
            pass

        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
        except:
            pass

        self.root.after(100, self.poll_updates)


# Thread execution target for Tkinter loop
def run_tkinter_ui():
    root = tk.Tk()
    app = BotUIApp(root)
    threading.Thread(target=hotkey_listener_thread, daemon=True).start()
    root.mainloop()


# Public interface functions
def ui_start(driver_instance=None):
    global active_driver
    active_driver = driver_instance
    threading.Thread(target=run_tkinter_ui, daemon=True).start()
    # Give the UI time to initialize, then show the LinkedIn reminder
    time.sleep(1.5)
    ui_alert(T("linkedin_title"), T("linkedin_msg"))

def ui_update_status(status_text, details_text=None, action_text=None):
    status_queue.put(("status", status_text))
    if details_text is not None:
        status_queue.put(("details", details_text))
    if action_text is not None:
        status_queue.put(("action", action_text))

def ui_alert(title, message):
    resp_q = queue.Queue()
    alert_queue.put((title, message, resp_q))
    resp_q.get()
    status_queue.put(("status", current_ui_status))
    status_queue.put(("details", current_ui_details))

def ui_confirm(title, message, buttons):
    resp_q = queue.Queue()
    alert_queue.put((title, message, resp_q, buttons))
    val = resp_q.get()
    status_queue.put(("status", current_ui_status))
    status_queue.put(("details", current_ui_details))
    return val

def ui_ask_text(title, question, placeholder=""):
    """Show a text-input dialog and return the entered string (empty string = skipped)."""
    resp_q = queue.Queue()
    alert_queue.put(("__ask_text__", title, question, placeholder, resp_q))
    val = resp_q.get()
    return val or ""

def ui_pause_check():
    """Called by the bot thread to check/block on pause state."""
    global is_paused, is_stopped

    if is_stopped:
        print("[BotUI] Stop triggered. Exiting...")
        try:
            if active_driver:
                active_driver.quit()
        except:
            pass
        os._exit(0)

    # Block bot thread while paused — the UI thread toggles is_paused via poll_updates
    while is_paused:
        time.sleep(0.1)
        if is_stopped:
            try:
                if active_driver:
                    active_driver.quit()
            except:
                pass
            os._exit(0)


def is_career_ops_mode():
    global career_ops_mode
    return career_ops_mode

_PLACEHOLDER_KEYS = {"YOUR_GROQ_API_KEY_HERE", "YOUR_API_KEY_HERE", "", "not-needed", "sk-xxx"}

def _is_api_key_missing() -> bool:
    """Returns True if use_AI is True but llm_api_key is still a placeholder."""
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SECR = os.path.join(_BASE, "config", "secrets.py")
    use_ai = _read_py_var(_SECR, "use_AI")
    if not use_ai:
        return False
    provider = str(_read_py_var(_SECR, "ai_provider") or "").lower()
    if provider == "gemini":
        return False  # Gemini key is stored elsewhere
    key = str(_read_py_var(_SECR, "llm_api_key") or "").strip()
    return key in _PLACEHOLDER_KEYS


def ui_enforce_configuration():
    """Checks if basic config is present. On first run, offers CV auto-setup wizard."""
    global is_paused
    from modules.bot_ui import _read_py_var
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _PERS = os.path.join(_BASE, "config", "personals.py")

    _SECR_PATH = os.path.join(_BASE, "config", "secrets.py")
    first_name = _read_py_var(_PERS, "first_name")
    missing_name = not first_name or str(first_name).strip() == ""
    missing_key  = _is_api_key_missing()

    if missing_name or missing_key:
        ui_update_status(T("status_config_req"), T("msg_config_req"))
        is_paused = True

        # ── First run: offer CV auto-configuration wizard ──────────────────
        if missing_name:
            try:
                from modules.cv_wizard import run_cv_wizard
                run_cv_wizard()
            except Exception as _wiz_err:
                print(f"[Setup] CV wizard error: {_wiz_err}")

        # ── If API key still missing after wizard, guide user ──────────────
        if _is_api_key_missing():
            ui_alert(T("alert_api_key_title"), T("alert_api_key_msg"))

        action_queue.put("open_settings")

        _wizard_offered_after_key = False
        while is_paused:
            time.sleep(0.5)
            new_first_name = _read_py_var(_PERS, "first_name")
            name_ok = bool(new_first_name and str(new_first_name).strip())
            key_ok  = not _is_api_key_missing()
            # Once API key is set but name still missing, offer CV wizard
            if key_ok and not name_ok and not _wizard_offered_after_key:
                _wizard_offered_after_key = True
                try:
                    from modules.cv_wizard import run_cv_wizard
                    run_cv_wizard()
                except Exception as _wiz_err:
                    print(f"[Setup] CV wizard retry error: {_wiz_err}")
            if name_ok and key_ok:
                is_paused = False
                ui_update_status(T("status_configured"), T("msg_bot_ready"))
                break

    # ── Check for empty search_terms even when name and key are already set ──
    if not _is_api_key_missing():
        try:
            from modules.cv_wizard import run_job_terms_wizard
            run_job_terms_wizard()
        except Exception as _e:
            print(f"[Setup] Job terms wizard error: {_e}")
