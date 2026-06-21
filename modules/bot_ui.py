import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import threading
import queue
import ctypes
import time
import os
import re
import ast
from ctypes import c_int, c_void_p, Structure, sizeof, windll, pointer, byref
from ctypes import wintypes

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
    try:
        policy = AccentPolicy(4, 2, color_abgr, 0)
        data = WindowCompositionAttributeData(
            19,
            ctypes.cast(pointer(policy), c_void_p),
            sizeof(policy)
        )
        windll.user32.SetWindowCompositionAttribute.restype = c_int
        windll.user32.SetWindowCompositionAttribute.argtypes = [c_void_p, c_void_p]
        windll.user32.SetWindowCompositionAttribute(hwnd, pointer(data))
    except Exception as e:
        print("[BotUI] Blur error:", e)

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
                        try:
                            if active_driver:
                                active_driver.quit()
                        except Exception:
                            pass
                        finally:
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
    def __init__(self, parent, title, message, response_queue):
        super().__init__(parent)
        self.response_queue = response_queue
        scaling = get_dpi_scaling()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.95)
        self.configure(bg="#050505")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = int(400 * scaling), int(200 * scaling)
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
        msg_label = tk.Label(frame, text=message, fg="#E6E6E8", bg="#0a0a0c", font=("Segoe UI", 9), justify="left", wraplength=int(370 * scaling), anchor="nw")
        msg_label.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        btn_frame = tk.Frame(frame, bg="#0a0a0c")
        btn_frame.pack(fill="x", side="bottom", pady=15)
        btn = tk.Button(btn_frame, text="CONTINUE", fg="#FFFFFE", bg="#7F5AF0", activeforeground="#FFFFFE", activebackground="#9270F2", bd=0, padx=15, pady=6, font=("Segoe UI Bold", 9), command=self.on_continue, cursor="hand2")
        btn.pack(side="right", padx=15)
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
        self.attributes("-alpha", 0.95)
        self.configure(bg="#050505")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = int(450 * scaling), int(220 * scaling)
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
        msg_label = tk.Label(frame, text=message, fg="#E6E6E8", bg="#0a0a0c", font=("Segoe UI", 9), justify="left", wraplength=int(420 * scaling), anchor="nw")
        msg_label.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        btn_frame = tk.Frame(frame, bg="#0a0a0c")
        btn_frame.pack(fill="x", side="bottom", pady=15)
        for idx, btn_text in enumerate(buttons):
            is_accent = (idx == len(buttons) - 1)
            bg_color = "#7F5AF0" if is_accent else "#2D2D30"
            active_bg = "#9270F2" if is_accent else "#3A3A3F"
            btn = tk.Button(btn_frame, text=btn_text.upper(), fg="#FFFFFE", bg=bg_color, activeforeground="#FFFFFE", activebackground=active_bg, bd=0, padx=12, pady=5, font=("Segoe UI Bold", 8), command=lambda val=btn_text: self.on_click(val), cursor="hand2")
            btn.pack(side="right", padx=8)
        self.bell()

    def on_click(self, value):
        self.response_queue.put(value)
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

    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
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

        tk.Label(hdr, text="  ⎔  CONFIGURACION", fg=ACCENT, bg=BG,
                 font=("Segoe UI Bold", 10)).pack(side="left", padx=8)

        close_lbl = tk.Label(hdr, text="  ✕  ", fg=FG_DIM, bg=BG,
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

        tabs = [("⌕  Búsqueda", "search"), ("≡  Personal", "personal"),
                ("✎  Respuestas", "responses"), ("⎔  Bot", "bot")]
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

        tk.Button(btn_bar, text="CANCELAR", fg=FG_DIM, bg=BG,
                  activeforeground=FG, activebackground=BG2,
                  bd=0, padx=14, pady=5, font=("Segoe UI Bold", 8),
                  command=self.destroy, cursor="hand2").pack(side="right", padx=8, pady=7)

        tk.Button(btn_bar, text="  GUARDAR  ", fg="#101012", bg=ACCENT2,
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

    # ── Build tabs ────────────────────────────────────────────────────────────

    def _build_all_tabs(self):
        for key in ["search", "personal", "responses", "bot"]:
            outer = tk.Frame(self._content, bg=BG2)
            inner = self._make_scroll_frame(outer)
            self._tab_frames[key] = outer
            getattr(self, f"_build_tab_{key}")(inner)

    def _build_tab_search(self, p):
        _section_title(p, "⌕  Términos de búsqueda y foco")
        self._add_list(p, "search_terms", "Términos de búsqueda (search_terms)", self._SEARCH, "search_terms", height=5)
        self._add_entry(p, "search_location", "Ubicación (search_location)", self._SEARCH, "search_location")

        _section_title(p, "⌕  Filtro de Relevancia")
        self._add_list(p, "primary_focus_keywords", "Palabras clave PRINCIPALES (Help Desk, Tech Support...)", self._SEARCH, "primary_focus_keywords", height=3)
        self._add_list(p, "secondary_focus_keywords", "Palabras clave SECUNDARIAS (solo Remote/Hybrid)", self._SEARCH, "secondary_focus_keywords", height=3)
        self._add_bool(p, "enable_job_focus_filter", "Activar filtro de relevancia (skip trabajos irrelevantes)", self._SEARCH, "enable_job_focus_filter")

        _section_title(p, "⎔  Filtros LinkedIn")
        self._add_entry(p, "switch_number", "Cambiar búsqueda cada N aplicaciones", self._SEARCH, "switch_number", width=10)
        self._add_entry(p, "date_posted", "Fecha publicado (Any time, Past week, Past 24 hours...)", self._SEARCH, "date_posted")
        self._add_entry(p, "sort_by", "Ordenar por (Most recent / Most relevant)", self._SEARCH, "sort_by")
        self._add_list(p, "on_site", "Modalidad (On-site, Remote, Hybrid)", self._SEARCH, "on_site", height=2)
        self._add_list(p, "experience_level", "Nivel de experiencia", self._SEARCH, "experience_level", height=2)
        self._add_bool(p, "easy_apply_only", "Solo Easy Apply", self._SEARCH, "easy_apply_only")
        self._add_bool(p, "randomize_search_order", "Aleatorizar orden de búsqueda", self._SEARCH, "randomize_search_order")

        _section_title(p, "✕  Palabras a evitar")
        self._add_list(p, "bad_words", "Palabras malas en descripción (bad_words)", self._SEARCH, "bad_words", height=3)
        self._add_list(p, "about_company_bad_words", "Palabras malas en empresa", self._SEARCH, "about_company_bad_words", height=2)
        self._add_entry(p, "current_experience", "Experiencia actual en años (-1 = ignorar)", self._SEARCH, "current_experience", width=10)

    def _build_tab_personal(self, p):
        _section_title(p, "≡  Datos personales")
        self._add_entry(p, "first_name", "Nombre (first_name)", self._PERS, "first_name")
        self._add_entry(p, "middle_name", "Segundo nombre (middle_name)", self._PERS, "middle_name")
        self._add_entry(p, "last_name", "Apellido (last_name)", self._PERS, "last_name")
        self._add_entry(p, "phone_number", "Teléfono (phone_number)", self._PERS, "phone_number")
        self._add_entry(p, "current_city", "Ciudad actual (current_city)", self._PERS, "current_city")
        self._add_entry(p, "state", "Estado/Departamento (state)", self._PERS, "state")
        self._add_entry(p, "country", "País (country)", self._PERS, "country")
        self._add_entry(p, "zipcode", "Código postal (zipcode)", self._PERS, "zipcode")
        self._add_entry(p, "street", "Calle (street)", self._PERS, "street")
        self._add_entry(p, "university", "Universidad (university)", self._PERS, "university")
        self._add_entry(p, "identification_number", "Número de identificación", self._PERS, "identification_number")

        _section_title(p, "⊜  Equal Opportunity")
        self._add_entry(p, "gender", "Género (Male/Female/Other/Decline)", self._PERS, "gender")
        self._add_entry(p, "ethnicity", "Etnia", self._PERS, "ethnicity")
        self._add_entry(p, "disability_status", "Discapacidad (Yes/No/Decline)", self._PERS, "disability_status")
        self._add_entry(p, "veteran_status", "Veterano (Yes/No/Decline)", self._PERS, "veteran_status")

    def _build_tab_responses(self, p):
        _section_title(p, "✎  Experiencia & Salario")
        self._add_entry(p, "years_of_experience", "Años de experiencia a reportar", self._QUEST, "years_of_experience", width=10)
        self._add_entry(p, "desired_salary", "Salario deseado (número)", self._QUEST, "desired_salary", width=16)
        self._add_entry(p, "current_ctc", "CTC actual (número)", self._QUEST, "current_ctc", width=16)
        self._add_entry(p, "notice_period", "Período de aviso en días", self._QUEST, "notice_period", width=10)
        self._add_entry(p, "require_visa", "¿Requiere visa? (Yes/No)", self._QUEST, "require_visa")
        self._add_entry(p, "recent_employer", "Empleador más reciente", self._QUEST, "recent_employer")
        self._add_entry(p, "confidence_level", "Nivel de confianza 1-10", self._QUEST, "confidence_level", width=10)
        self._add_entry(p, "us_citizenship", "Ciudadanía US", self._QUEST, "us_citizenship")

        _section_title(p, "⎔  Links")
        self._add_entry(p, "linkedIn", "URL de LinkedIn", self._QUEST, "linkedIn")
        self._add_entry(p, "website", "Portfolio / Website", self._QUEST, "website")

        _section_title(p, "✎  Textos largos")
        self._add_entry(p, "linkedin_headline", "Titular de LinkedIn", self._QUEST, "linkedin_headline")
        self._add_text(p, "linkedin_summary", "Resumen de LinkedIn", self._QUEST, "linkedin_summary", height=5)
        self._add_text(p, "cover_letter", "Carta de presentación", self._QUEST, "cover_letter", height=8)
        self._add_text(p, "user_information_all", "Información completa para IA", self._QUEST, "user_information_all", height=8)
        self._add_entry(p, "default_resume_path", "Ruta del CV (PDF)", self._QUEST, "default_resume_path", browse=True)

    def _build_tab_bot(self, p):
        _section_title(p, "⎔  Comportamiento del Bot")
        self._add_bool(p, "pause_before_submit", "Pausar antes de enviar cada aplicación", self._QUEST, "pause_before_submit")
        self._add_bool(p, "pause_at_failed_question", "Pausar si no puede responder una pregunta", self._QUEST, "pause_at_failed_question")
        self._add_bool(p, "overwrite_previous_answers", "Sobreescribir respuestas anteriores", self._QUEST, "overwrite_previous_answers")
        self._add_bool(p, "run_non_stop", "Correr sin parar (run_non_stop)", self._SETT, "run_non_stop")
        self._add_bool(p, "follow_companies", "Seguir empresas al aplicar", self._SETT, "follow_companies")
        self._add_bool(p, "close_tabs", "Cerrar tabs de aplicaciones externas", self._SETT, "close_tabs")

        _section_title(p, "⎔  Navegador & Performance")
        self._add_entry(p, "click_gap", "Pausa entre clicks (seg)", self._SETT, "click_gap", width=10)
        self._add_bool(p, "run_in_background", "Correr en fondo (sin Chrome visible)", self._SETT, "run_in_background")
        self._add_bool(p, "smooth_scroll", "Scroll suave", self._SETT, "smooth_scroll")
        self._add_bool(p, "stealth_mode", "Modo stealth (anti-bot)", self._SETT, "stealth_mode")
        self._add_bool(p, "safe_mode", "Modo seguro (perfil invitado)", self._SETT, "safe_mode")
        self._add_bool(p, "keep_screen_awake", "Mantener pantalla activa", self._SETT, "keep_screen_awake")

        _section_title(p, "🔄  Ciclos de búsqueda")
        self._add_bool(p, "alternate_sortby", "Alternar orden de búsqueda", self._SETT, "alternate_sortby")
        self._add_bool(p, "cycle_date_posted", "Ciclar filtro de fecha", self._SETT, "cycle_date_posted")
        self._add_bool(p, "stop_date_cycle_at_24hr", "Parar ciclo en 24hr", self._SETT, "stop_date_cycle_at_24hr")

    # ── Save logic ────────────────────────────────────────────────────────────

    def _save_all(self):
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
                else:
                    continue

                ok = _write_py_var(filepath, varname, val)
                if not ok:
                    errors.append(f"{varname}")
            except Exception as e:
                errors.append(f"{varname}: {e}")

        if errors:
            self._show_result(f"⚠ Errores en: {', '.join(errors)}", error=True)
        else:
            self._show_result("✓ Configuración guardada correctamente")

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
        root.attributes("-alpha", 0.85)
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

        # Close button (X)
        self.close_btn = tk.Label(self.header, text="✕", fg="#94A1B2",
                                  bg="#0a0a0c", font=("Segoe UI Bold", 10),
                                  cursor="hand2")
        self.close_btn.pack(side="right", padx=(8, 0))
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="#E74C3C"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg="#94A1B2"))
        self.close_btn.bind("<Button-1>", lambda e: self.trigger_stop())

        # ⚙ Settings gear button — discrete, right of title
        self.gear_btn = tk.Label(self.header, text="⚙", fg="#4c4c52",
                                 bg="#0a0a0c", font=("Segoe UI", 10),
                                 cursor="hand2")
        self.gear_btn.pack(side="right", padx=(0, 4))
        self.gear_btn.bind("<Enter>", lambda e: self.gear_btn.config(fg=ACCENT))
        self.gear_btn.bind("<Leave>", lambda e: self.gear_btn.config(fg="#4c4c52"))
        self.gear_btn.bind("<Button-1>", lambda e: self._open_settings())

        # Drag indicator label
        self.drag_lbl = tk.Label(self.header, text="⠿", fg="#4c4c52",
                                 bg="#0a0a0c", font=("Segoe UI", 10))
        self.drag_lbl.pack(side="right")

        # Buttons Container
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
                                   wrap="word", cursor="arrow")
        self.console_box.pack(fill="both", expand=True, padx=6, pady=4)

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
        self.pause_btn = tk.Button(self.btn_frame, text="PAUSE",
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
        self.optimize_btn = tk.Button(self.btn_frame, text="OPTIMIZAR CV",
                                      fg="#FFFFFE", bg="#2D2D30",
                                      activeforeground="#FFFFFE",
                                      activebackground="#3A3A3F",
                                      bd=0, padx=8, pady=4,
                                      font=("Segoe UI Bold", 8),
                                      command=self._trigger_optimize_cv,
                                      cursor="hand2")
        self.optimize_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Stop Button
        self.stop_btn = tk.Button(self.btn_frame, text="STOP",
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
        self.add_log("System", "CVSniper Control initialized.", "system")

        self.poll_updates()

    def _open_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        self._settings_win = GlassSettings(self.root)

    def _trigger_optimize_cv(self):
        threading.Thread(target=self._optimize_cv_flow, daemon=True).start()

    def _optimize_cv_flow(self):
        choice = ui_confirm("Optimizador de CV", "¿Deseas optimizar un CV existente o empezar de cero usando tus datos de configuración?", ["EXISTENTE", "DE CERO"])
        if not choice:
            return
        if choice == "EXISTENTE":
            file_path = filedialog.askopenfilename(title="Seleccionar CV Viejo", filetypes=[("Archivos PDF", "*.pdf")])
            if not file_path:
                return
            inc_port = ui_confirm("Portfolio", "¿Deseas incluir la página del Portfolio visual al final del CV?", ["SI", "NO"])
            self.add_log("System", "Optimizando CV con Inteligencia Artificial...", "system")
            try:
                from modules.ai.openaiConnections import ai_optimize_existing_cv
                success = ai_optimize_existing_cv(file_path, include_portfolio=(inc_port=="SI"))
            except Exception as ex:
                self.add_log("System", f"Excepción: {ex}", "status")
                success = False
            if success:
                self.add_log("System", "CV Optimizado guardado en 'all resumes/'.", "status")
                ui_alert("¡Éxito!", "Se generó exitosamente tu CV optimizado y llamativo.")
            else:
                self.add_log("System", "Error al optimizar CV. Revisa la consola para más detalles.", "status")
        elif choice == "DE CERO":
            inc_port = ui_confirm("Portfolio", "¿Deseas incluir la página del Portfolio visual al final del CV?", ["SI", "NO"])
            self.add_log("System", "Generando CV llamativo con tus datos de configuración...", "system")
            try:
                from modules.ai.openaiConnections import ai_generate_cv_from_config
                success = ai_generate_cv_from_config(include_portfolio=(inc_port=="SI"))
            except Exception as ex:
                self.add_log("System", f"Excepción: {ex}", "status")
                success = False
            if success:
                self.add_log("System", "CV Generado guardado en 'all resumes/'.", "status")
                ui_alert("¡Éxito!", "Se generó exitosamente tu CV llamativo a partir de tu información básica.")
            else:
                self.add_log("System", "Error al generar CV desde cero. Revisa la consola.", "status")

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
        if self.stop_btn.cget("text") == "STOP":
            self.stop_btn.config(text="CONFIRM?", bg="#FF6B35")
            self.add_log("System", "Click CONFIRM? again to stop the bot.", "system")
            self.root.after(3000, self._reset_stop_btn)
            return
        self.add_log("System", "Stopping bot...", "system")
        self.stop_btn.config(text="STOPPING...", bg="#8B0000", state="disabled")
        self.dot_canvas.itemconfig(self.status_dot, fill="#E74C3C")
        self.root.update()

        def _kill():
            try:
                if active_driver:
                    active_driver.quit()
            except Exception:
                pass
            finally:
                os._exit(0)

        threading.Thread(target=_kill, daemon=True).start()

    def _reset_stop_btn(self):
        if self.stop_btn.cget("text") == "CONFIRM?":
            self.stop_btn.config(text="STOP", bg="#E74C3C")

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
            self.add_log("Alert", f"Action required: {item[0]}", "status")
            if len(item) == 4:
                title, message, resp_q, buttons = item
                self.dot_canvas.itemconfig(self.status_dot, fill="#F1C40F")
                GlassConfirm(self.root, title, message, buttons, resp_q)
            else:
                title, message, resp_q = item
                self.dot_canvas.itemconfig(self.status_dot, fill="#F1C40F")
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

        # 4. Handle pause/resume state updates visually
        if is_paused != self.last_pause_state:
            self.last_pause_state = is_paused
            if is_paused:
                self.add_log("System", "Bot pausado.", "system")
            else:
                self.add_log("System", "Bot reanudado.", "system")

        if is_paused:
            self.pause_btn.config(text="RESUME", bg="#00E8C6", fg="#101012",
                                  activebackground="#00C9AA")
            self.dot_canvas.itemconfig(self.status_dot, fill="#F1C40F")
        else:
            self.pause_btn.config(text="PAUSE", bg="#2D2D30", fg="#FFFFFE",
                                  activebackground="#3A3A3F")
            if is_stopped:
                self.dot_canvas.itemconfig(self.status_dot, fill="#E74C3C")
            else:
                self.dot_canvas.itemconfig(self.status_dot, fill="#2ECC71")

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

def ui_enforce_configuration():
    """Checks if basic config is present, blocks and opens settings if not."""
    global is_paused
    from modules.bot_ui import _read_py_var
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _PERS = os.path.join(_BASE, "config", "personals.py")
    
    first_name = _read_py_var(_PERS, "first_name")
    
    if not first_name or str(first_name).strip() == "":
        ui_update_status("Configuración requerida", "Por favor completa tus datos en la configuración.")
        is_paused = True
        ui_alert("Configuración Inicial Requerida", "Es la primera vez que ejecutas el bot o faltan tus datos personales. Se abrirá la rueda de configuración. ¡Llénala y guarda los cambios para continuar!")
        # Put an action to the queue to open settings on the UI thread
        action_queue.put("open_settings")
        
        while is_paused:
            time.sleep(0.5)
            # Re-check inside loop just in case they saved
            new_first_name = _read_py_var(_PERS, "first_name")
            if new_first_name and str(new_first_name).strip() != "":
                is_paused = False
                ui_update_status("Status: Configurado", "Bot listo para continuar.")
                break
