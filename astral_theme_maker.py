"""
Astral Theme Maker
A standalone app for creating color themes for Astral IDE.
Themes are saved to  .astral_custom_themes.json  in the same folder as this file.
The IDE automatically picks up that file on next launch.
"""

import json
import re
import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog
from pathlib import Path

# Save themes in user's home directory for exe compatibility
THEMES_FILE = Path.home() / ".astral_custom_themes.json"

# ── key definitions ────────────────────────────────────────────────────────────

UI_KEYS: list[tuple[str, str]] = [
    ("window_bg",       "Window Background"),
    ("panel_bg",        "Panel Background"),
    ("panel_fg",        "Panel Text"),
    ("tab_bg",          "Tab Background"),
    ("tab_fg",          "Tab Text"),
    ("tab_selected_bg", "Active Tab Background"),
    ("tab_selected_fg", "Active Tab Text"),
    ("editor_bg",       "Editor Background"),
    ("editor_fg",       "Editor Text"),
    ("output_bg",       "Output Background"),
    ("output_fg",       "Output Text"),
    ("readme_bg",       "README Preview Background"),
    ("readme_fg",       "README Preview Text"),
]

SYNTAX_KEYS: list[tuple[str, str]] = [
    ("keyword",       "Keyword"),
    ("builtin",       "Builtin"),
    ("literal",       "Literal  (true / false / null)"),
    ("number",        "Number"),
    ("operator",      "Operator"),
    ("string",        "String"),
    ("fstring",       "F-String"),
    ("fstring_brace", "F-String Braces  { }"),
    ("fn_def",        "Function Definition Name"),
    ("fn_call",       "Function Call"),
    ("comment",       "Comment"),
]

DEFAULT_THEME: dict[str, str] = {
    "window_bg": "#0B1220", "panel_bg": "#1E293B", "panel_fg": "#E5E7EB",
    "tab_bg": "#334155", "tab_fg": "#E5E7EB",
    "tab_selected_bg": "#0F172A", "tab_selected_fg": "#F8FAFC",
    "editor_bg": "#0F172A", "editor_fg": "#E5E7EB",
    "output_bg": "#111827", "output_fg": "#E5E7EB",
    "readme_bg": "#111827", "readme_fg": "#E5E7EB",
    "keyword": "#60A5FA", "builtin": "#F472B6", "literal": "#2DD4BF",
    "number": "#FB923C", "operator": "#38BDF8",
    "string": "#6EE7B7", "fstring": "#6EE7B7", "fstring_brace": "#FFFFFF",
    "fn_def": "#FCD34D", "fn_call": "#93C5FD", "comment": "#94A3B8",
}

SAMPLE_CODE = """\
// A simple example
fn greet(name) {
    let count = len(name)
    let msg = f"Hello, {name}! ({count} chars)"
    if count > 5 {
        return msg
    }
    return "Hi!"
}

let result = greet("World")
print(result)
let x = 42 + 3.14
let ok = true
"""

README_SAMPLE = """\
# Astral IDE

- README preview colors can be customized.
- This sample shows README text styling only.

Use themes to control readability.
"""

_KEYWORDS = {"fn", "let", "if", "elif", "else", "while", "for", "return", "in"}
_BUILTINS = {"print", "len", "str", "int", "float", "type", "input"}
_LITERALS = {"true", "false", "null"}

# ── helper ─────────────────────────────────────────────────────────────────────


def _contrast(hex_color: str) -> str:
    """Return black or white for best contrast on hex_color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#FFFFFF"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else "#FFFFFF"


# ── main app ───────────────────────────────────────────────────────────────────

class ThemeMaker(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Astral Theme Maker")
        self.geometry("1150x700")
        self.minsize(920, 580)
        self.configure(background="#1A1A2E")

        self.themes: dict[str, dict] = {}
        self._load_themes_file()

        self._color_vars:    dict[str, tk.StringVar] = {}
        self._color_buttons: dict[str, tk.Button] = {}
        self._current_theme: str | None = None

        self._build_ui()
        self._refresh_list()

    # ── persistence ────────────────────────────────────────────────────────────

    def _load_themes_file(self) -> None:
        if THEMES_FILE.exists():
            try:
                data = json.loads(THEMES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.themes = data
            except Exception:
                pass
        if not self.themes:
            self.themes["My Theme"] = dict(DEFAULT_THEME)

    def _save_themes_file(self) -> None:
        THEMES_FILE.write_text(
            json.dumps(self.themes, indent=2), encoding="utf-8")

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0, minsize=220)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0, minsize=380)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    # ── left: theme list ───────────────────────────────────────────────────────

    def _build_left_panel(self) -> None:
        left = tk.Frame(self, bg="#16213E")
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        tk.Label(left, text="Themes", bg="#16213E", fg="#E5E7EB",
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        # action buttons
        btn_row = tk.Frame(left, bg="#16213E")
        btn_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        for text, cmd in [("+ New",   self._new_theme),
                          ("Copy",    self._copy_theme),
                          ("Rename",  self._rename_theme),
                          ("Delete",  self._delete_theme)]:
            tk.Button(btn_row, text=text, command=cmd,
                      bg="#334155", fg="#E5E7EB", relief="flat",
                      font=("Segoe UI", 9), padx=7, pady=3,
                      activebackground="#475569", activeforeground="#FFFFFF",
                      cursor="hand2").pack(side="left", padx=2)

        # listbox
        lf = tk.Frame(left, bg="#16213E")
        lf.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self._theme_listbox = tk.Listbox(
            lf, bg="#0F172A", fg="#E5E7EB",
            selectbackground="#2563EB", selectforeground="#FFFFFF",
            relief="flat", borderwidth=0, font=("Segoe UI", 10),
            activestyle="none")
        self._theme_listbox.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(lf, orient="vertical",
                          command=self._theme_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._theme_listbox.configure(yscrollcommand=sb.set)
        self._theme_listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # save
        tk.Button(left, text="💾  Save Themes File", command=self._on_save,
                  bg="#2563EB", fg="#FFFFFF", relief="flat",
                  font=("Segoe UI", 10, "bold"), pady=8,
                  activebackground="#1D4ED8", cursor="hand2").grid(
            row=3, column=0, sticky="ew", padx=8, pady=(0, 8))

    # ── center: scrollable color rows ──────────────────────────────────────────

    def _build_center_panel(self) -> None:
        center = tk.Frame(self, bg="#1A1A2E")
        center.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        tk.Label(center, text="Theme Colors", bg="#1A1A2E", fg="#E5E7EB",
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        canvas = tk.Canvas(center, bg="#1A1A2E", highlightthickness=0)
        vsb = tk.Scrollbar(center, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

        self._color_frame = tk.Frame(canvas, bg="#1A1A2E")
        cwin = canvas.create_window(
            (0, 0), window=self._color_frame, anchor="nw")
        self._color_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(cwin, width=e.width))
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._build_color_rows()

    def _build_color_rows(self) -> None:
        f = self._color_frame
        row = 0

        def section(label: str) -> None:
            nonlocal row
            tk.Label(f, text=label, bg="#1A1A2E", fg="#94A3B8",
                     font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w",
                padx=4, pady=(14, 3))
            row += 1

        def color_row(key: str, label: str) -> None:
            nonlocal row
            var = tk.StringVar(value="#000000")
            self._color_vars[key] = var

            tk.Label(f, text=label, bg="#1A1A2E", fg="#CBD5E1",
                     font=("Segoe UI", 9), anchor="w", width=28).grid(
                row=row, column=0, sticky="w", padx=(4, 0), pady=2)

            swatch = tk.Button(
                f, width=3, relief="flat", cursor="hand2", bd=1,
                command=lambda k=key: self._pick_color(k))
            swatch.grid(row=row, column=1, padx=(6, 3), pady=2)
            self._color_buttons[key] = swatch

            entry = tk.Entry(f, textvariable=var, width=10,
                             bg="#0F172A", fg="#E5E7EB",
                             insertbackground="#E5E7EB",
                             relief="flat", font=("Consolas", 9))
            entry.grid(row=row, column=2, padx=(0, 4), pady=2, sticky="w")
            entry.bind("<FocusOut>", lambda e, k=key: self._on_hex_entry(k))
            entry.bind("<Return>", lambda e, k=key: self._on_hex_entry(k))
            row += 1

        section("— UI Colors")
        for k, lbl in UI_KEYS:
            color_row(k, lbl)
        section("— Syntax Colors")
        for k, lbl in SYNTAX_KEYS:
            color_row(k, lbl)

    # ── right: live preview ────────────────────────────────────────────────────

    def _build_right_panel(self) -> None:
        right = tk.Frame(self, bg="#1A1A2E")
        right.grid(row=0, column=2, sticky="nsew", padx=(0, 8), pady=8)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(3, weight=2)
        right.columnconfigure(0, weight=1)

        tk.Label(right, text="Live Preview", bg="#1A1A2E", fg="#E5E7EB",
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        self._preview = tk.Text(
            right, font=("Consolas", 10), relief="flat",
            wrap="none", state="disabled",
            padx=10, pady=10)
        self._preview.grid(row=1, column=0, sticky="nsew")

        tk.Label(right, text="README Preview Sample", bg="#1A1A2E", fg="#E5E7EB",
                 font=("Segoe UI", 11, "bold")).grid(
            row=2, column=0, sticky="w", pady=(10, 6))

        self._readme_preview = tk.Text(
            right, font=("Consolas", 10), relief="flat",
            wrap="word", state="disabled",
            padx=10, pady=10)
        self._readme_preview.grid(row=3, column=0, sticky="nsew")

        self._setup_preview_tags()
        self._render_preview()
        self._render_readme_preview()

    def _setup_preview_tags(self) -> None:
        p = self._preview
        p.tag_configure("tok_comment",      font=("Consolas", 10, "italic"))
        p.tag_configure("tok_keyword",      font=("Consolas", 10, "bold"))
        p.tag_configure("tok_fn_def",       font=("Consolas", 10, "bold"))
        p.tag_configure("tok_literal",      font=("Consolas", 10, "bold"))
        p.tag_configure("tok_fstring_brace", font=("Consolas", 10, "bold"))
        for tag in ["tok_fn_call", "tok_builtin", "tok_number",
                    "tok_operator", "tok_string", "tok_fstring"]:
            p.tag_configure(tag, font=("Consolas", 10))

    def _render_preview(self) -> None:
        p = self._preview
        p.configure(state="normal")
        p.delete("1.0", tk.END)
        p.insert("1.0", SAMPLE_CODE)

        text = SAMPLE_CODE

        def hp(pattern: str, tag: str, flags: int = 0) -> None:
            for m in re.finditer(pattern, text, flags):
                p.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

        def hgp(pattern: str, grp: int, tag: str) -> None:
            for m in re.finditer(pattern, text):
                p.tag_add(tag, f"1.0+{m.start(grp)}c", f"1.0+{m.end(grp)}c")

        hp(r"\b\d+(?:\.\d+)?\b", "tok_number")
        hp(r"(?:==|!=|<=|>=|[+\-*/%<>!])", "tok_operator")
        for t in _LITERALS:
            hp(rf"\b{re.escape(t)}\b", "tok_literal")
        for t in _BUILTINS:
            hp(rf"\b{re.escape(t)}\b", "tok_builtin")
        for t in _KEYWORDS:
            hp(rf"\b{re.escape(t)}\b", "tok_keyword")
        hp(r"\b([A-Za-z_]\w*)(?=\s*\()", "tok_fn_call")
        hgp(r"\bfn\s+([A-Za-z_]\w*)", 1, "tok_fn_def")
        string_spans: list[tuple[int, int, bool]] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] != '"':
                i += 1
                continue
            is_fstring = False
            span_start = i
            if i > 0 and text[i - 1] in "fF":
                prev = text[i - 2] if i - 2 >= 0 else ""
                if not (prev.isalnum() or prev == "_"):
                    is_fstring = True
                    span_start = i - 1
            j = i + 1
            escaped = False
            while j < n:
                ch = text[j]
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    j += 1
                    break
                j += 1
            string_spans.append((span_start, min(j, n), is_fstring))
            i = max(j, i + 1)

        for s, e, is_f in string_spans:
            if not is_f:
                p.tag_add("tok_string", f"1.0+{s}c", f"1.0+{e}c")

        for s, e, is_f in string_spans:
            if not is_f:
                continue
            ftext, fbase = text[s:e], s
            spans = [(m.start(), m.end())
                     for m in re.finditer(r"\{[^}]*\}", ftext)]
            prev = 0
            for es, ee in spans:
                if prev < es:
                    p.tag_add("tok_fstring",
                              f"1.0+{fbase+prev}c", f"1.0+{fbase+es}c")
                prev = ee
            if prev < len(ftext):
                p.tag_add("tok_fstring",
                          f"1.0+{fbase+prev}c", f"1.0+{fbase+len(ftext)}c")
            for es, ee in spans:
                p.tag_add("tok_fstring_brace",
                          f"1.0+{fbase+es}c",   f"1.0+{fbase+es+1}c")
                p.tag_add("tok_fstring_brace",
                          f"1.0+{fbase+ee-1}c", f"1.0+{fbase+ee}c")
        hp(r"//.*$", "tok_comment", flags=re.MULTILINE)
        for tag in ["tok_number", "tok_operator", "tok_literal", "tok_builtin",
                    "tok_fn_call", "tok_keyword", "tok_fn_def",
                    "tok_fstring", "tok_string", "tok_comment", "tok_fstring_brace"]:
            p.tag_raise(tag)

        p.configure(state="disabled")

    def _render_readme_preview(self) -> None:
        p = self._readme_preview
        p.configure(state="normal")
        p.delete("1.0", tk.END)
        p.insert("1.0", README_SAMPLE)
        p.configure(state="disabled")

    def _apply_preview_colors(self) -> None:
        v = self._color_vars
        p = self._preview
        p.configure(bg=v["editor_bg"].get(), fg=v["editor_fg"].get())
        self._readme_preview.configure(
            bg=v["readme_bg"].get(), fg=v["readme_fg"].get())
        p.tag_configure("tok_comment",       foreground=v["comment"].get())
        p.tag_configure("tok_keyword",       foreground=v["keyword"].get())
        p.tag_configure("tok_fn_def",        foreground=v["fn_def"].get())
        p.tag_configure("tok_fn_call",       foreground=v["fn_call"].get())
        p.tag_configure("tok_builtin",       foreground=v["builtin"].get())
        p.tag_configure("tok_literal",       foreground=v["literal"].get())
        p.tag_configure("tok_number",        foreground=v["number"].get())
        p.tag_configure("tok_operator",      foreground=v["operator"].get())
        p.tag_configure("tok_string",        foreground=v["string"].get())
        p.tag_configure("tok_fstring",       foreground=v["fstring"].get())
        p.tag_configure("tok_fstring_brace",
                        foreground=v["fstring_brace"].get())

    # ── theme list actions ─────────────────────────────────────────────────────

    def _refresh_list(self, select: str | None = None) -> None:
        self._theme_listbox.delete(0, tk.END)
        for name in self.themes:
            self._theme_listbox.insert(tk.END, name)
        target = select if (select and select in self.themes) else (
            list(self.themes)[0] if self.themes else None)
        if target:
            idx = list(self.themes).index(target)
            self._theme_listbox.selection_set(idx)
            self._theme_listbox.activate(idx)
            self._load_into_editor(target)

    def _on_list_select(self, _event=None) -> None:
        sel = self._theme_listbox.curselection()
        if not sel:
            return
        self._flush_to_dict()
        self._load_into_editor(self._theme_listbox.get(sel[0]))

    def _load_into_editor(self, name: str) -> None:
        self._current_theme = name
        data = self.themes.get(name, DEFAULT_THEME)
        for key, var in self._color_vars.items():
            val = data.get(key, DEFAULT_THEME.get(key, "#000000"))
            var.set(val)
            btn = self._color_buttons.get(key)
            if btn:
                fg = _contrast(val)
                btn.configure(bg=val, activebackground=val,
                              fg=fg, activeforeground=fg, text="  ")
        self._apply_preview_colors()

    def _flush_to_dict(self) -> None:
        if self._current_theme is None:
            return
        self.themes[self._current_theme] = {k: v.get()
                                            for k, v in self._color_vars.items()}

    def _new_theme(self) -> None:
        name = simpledialog.askstring("New Theme", "Theme name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.themes:
            messagebox.showerror(
                "Exists", f'"{name}" already exists.', parent=self)
            return
        self.themes[name] = dict(DEFAULT_THEME)
        self._refresh_list(select=name)

    def _copy_theme(self) -> None:
        if not self._current_theme:
            return
        self._flush_to_dict()
        name = simpledialog.askstring(
            "Copy Theme", f'Name for copy of "{self._current_theme}":',
            parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.themes:
            messagebox.showerror(
                "Exists", f'"{name}" already exists.', parent=self)
            return
        self.themes[name] = dict(self.themes[self._current_theme])
        self._refresh_list(select=name)

    def _rename_theme(self) -> None:
        if not self._current_theme:
            return
        old = self._current_theme
        name = simpledialog.askstring("Rename Theme", "New name:",
                                      initialvalue=old, parent=self)
        if not name or not name.strip() or name.strip() == old:
            return
        name = name.strip()
        if name in self.themes:
            messagebox.showerror(
                "Exists", f'"{name}" already exists.', parent=self)
            return
        # preserve insertion order
        self.themes = {(name if k == old else k): v
                       for k, v in self.themes.items()}
        self._current_theme = name
        self._refresh_list(select=name)

    def _delete_theme(self) -> None:
        if not self._current_theme:
            return
        if len(self.themes) <= 1:
            messagebox.showwarning("Cannot Delete",
                                   "Keep at least one theme.", parent=self)
            return
        if not messagebox.askyesno("Delete", f'Delete "{self._current_theme}"?',
                                   parent=self):
            return
        self.themes.pop(self._current_theme)
        self._current_theme = None
        self._refresh_list()

    def _on_save(self) -> None:
        self._flush_to_dict()
        self._save_themes_file()
        messagebox.showinfo("Saved",
                            f"Themes saved to:\n{THEMES_FILE}\n\n"
                            "Restart Astral IDE to pick up new themes.",
                            parent=self)

    # ── color picker ───────────────────────────────────────────────────────────

    def _pick_color(self, key: str) -> None:
        current = self._color_vars[key].get()
        try:
            _, hex_color = colorchooser.askcolor(
                color=current, title=f"Color — {key}", parent=self)
        except Exception:
            hex_color = None
        if hex_color:
            self._set_color(key, hex_color.upper())

    def _set_color(self, key: str, hex_color: str) -> None:
        self._color_vars[key].set(hex_color)
        btn = self._color_buttons.get(key)
        if btn:
            fg = _contrast(hex_color)
            btn.configure(bg=hex_color, activebackground=hex_color,
                          fg=fg, activeforeground=fg, text="  ")
        self._apply_preview_colors()

    def _on_hex_entry(self, key: str) -> None:
        val = self._color_vars[key].get().strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", val):
            self._set_color(key, val.upper())


if __name__ == "__main__":
    app = ThemeMaker()
    app.mainloop()
