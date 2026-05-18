from __future__ import annotations
from astral.parser import ParseError, Parser
from astral.lexer import Lexer, LexerError
from astral.interpreter import Interpreter, RuntimeErrorPebble

import builtins as py_builtins
import io
import json
import keyword
import os
import re
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk
from unittest.mock import patch

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

try:
    from markdown import markdown as markdown_to_html
except Exception:
    markdown_to_html = None

try:
    from tkinterweb import HtmlFrame
except Exception:
    HtmlFrame = None

PROJECT_ROOT = Path(__file__).resolve().parent
# Save settings in user's home directory for exe compatibility
SETTINGS_PATH = Path.home() / ".astral_ide_settings.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


KEYWORDS = {"fn", "return", "let", "if", "class", "import", "this",
            "elif", "else", "while", "and", "or", "not"}
BUILTINS = {"print", "input", "len"}
LITERALS = {"true", "false", "nil"}

PY_KEYWORDS = set(keyword.kwlist)
PY_BUILTINS = {
    name
    for name in dir(py_builtins)
    if not name.startswith("_") and callable(getattr(py_builtins, name, None))
}
PY_LITERALS = {"True", "False", "None"}
APP_VERSION = "1.0.0"


class AstralIDE(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Astral IDE")
        self.geometry("1100x700")
        self.style = ttk.Style(self)
        # Use a ttk theme that reliably applies custom tab foreground/background colors.
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.current_file: Path | None = None
        self.workspace_root: Path | None = PROJECT_ROOT
        self._dirty = False
        self._highlight_job: str | None = None
        self._autocomplete_window: tk.Toplevel | None = None
        self._autocomplete_listbox: tk.Listbox | None = None
        self._autocomplete_start: str | None = None
        self._tree_paths: dict[str, Path] = {}
        self._readme_preview_images: list[object] = []
        html_preview_requested = os.environ.get(
            "ASTRAL_ENABLE_HTML_README_PREVIEW", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._readme_preview_uses_html = bool(
            html_preview_requested and markdown_to_html is not None and HtmlFrame is not None
        )
        self._readme_preview_bg = "#111827"
        self._readme_preview_fg = "#E5E7EB"

        self.font_size_var = tk.IntVar(value=11)
        self.font_family_var = tk.StringVar(value="Consolas")
        self.theme_var = tk.StringVar(value="Astral Light")
        self.language_var = tk.StringVar(value="Astral")
        self.autocomplete_var = tk.BooleanVar(value=True)
        self.autosave_on_run_var = tk.BooleanVar(value=False)
        self.autosave_on_switch_var = tk.BooleanVar(value=False)

        self._load_settings()

        self._build_ui()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_title()
        self._set_status("Ready")

    def _build_ui(self) -> None:
        self.toolbar = ttk.Frame(self, style="Astral.TFrame")
        self.toolbar.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Button(self.toolbar, style="Astral.TButton", text="New", command=self.new_file).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Open", command=self.open_file).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Open Folder", command=self.open_folder).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Save", command=self.save_file).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Run",
                   command=self.run_code).pack(side=tk.LEFT)
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(self.toolbar, style="Astral.TButton", text="Fn Template", command=self.insert_astral_function_template).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Class Template", command=self.insert_astral_class_template).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Check Astral", command=self.check_astral_syntax).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(self.toolbar, style="Astral.TButton", text="Insert Timestamp", command=self.insert_timestamp).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Doc Stats", command=self.show_document_stats).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="Format JSON", command=self.format_json_document).pack(
            side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.toolbar, style="Astral.TButton", text="README Preview", command=self.show_readme_preview).pack(
            side=tk.LEFT, padx=(0, 6))

        self.notebook = ttk.Notebook(self, style="Astral.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        editor_frame = ttk.Frame(self.notebook, style="Astral.TFrame")
        output_frame = ttk.Frame(self.notebook, style="Astral.TFrame")
        readme_frame = ttk.Frame(self.notebook, style="Astral.TFrame")
        settings_frame = ttk.Frame(self.notebook, style="Astral.TFrame")
        self._readme_frame = readme_frame
        self.notebook.add(editor_frame, text="Editor")
        self.notebook.add(output_frame, text="Output")
        self.notebook.add(readme_frame, text="README Preview")
        self.notebook.add(settings_frame, text="Settings")

        editor_split = ttk.Panedwindow(editor_frame, orient=tk.HORIZONTAL)
        editor_split.pack(fill=tk.BOTH, expand=True)

        explorer_frame = ttk.Frame(editor_split, style="Astral.TFrame")
        code_frame = ttk.Frame(editor_split, style="Astral.TFrame")
        editor_split.add(explorer_frame, weight=1)
        editor_split.add(code_frame, weight=4)

        explorer_toolbar = ttk.Frame(explorer_frame, style="Astral.TFrame")
        explorer_toolbar.pack(fill=tk.X, padx=6, pady=(6, 4))
        ttk.Button(explorer_toolbar, style="Astral.TButton", text="Refresh", command=self.refresh_file_tree).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(explorer_toolbar, style="Astral.TButton", text="New Folder", command=self.new_folder).pack(
            side=tk.LEFT, padx=(0, 6)
        )

        self.workspace_label_var = tk.StringVar(value="Workspace: (none)")
        ttk.Label(explorer_frame, style="Astral.TLabel", textvariable=self.workspace_label_var).pack(
            fill=tk.X, padx=6, pady=(0, 4)
        )

        self.file_tree = ttk.Treeview(
            explorer_frame, show="tree", style="Astral.Treeview")
        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self.file_tree.bind("<Double-1>", self._open_selected_tree_item)

        self.editor = tk.Text(code_frame, wrap=tk.NONE,
                              undo=True, font=(self.font_family_var.get(), self.font_size_var.get()))
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<KeyRelease>", self._on_key_release)
        self.editor.bind("<Control-space>", self._trigger_autocomplete)
        self.editor.bind("<Tab>", self._accept_autocomplete)
        self.editor.bind("<Return>", self._accept_autocomplete)
        self.editor.bind("<Escape>", self._close_autocomplete)
        self.editor.bind("<Up>", self._autocomplete_prev)
        self.editor.bind("<Down>", self._autocomplete_next)
        self._configure_editor_tags(
            self.font_size_var.get(), self.font_family_var.get())

        self.output = tk.Text(output_frame, wrap=tk.WORD, height=10, font=(
            self.font_family_var.get(), max(9, self.font_size_var.get() - 1)), state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True)

        self.readme_preview_html = None
        self.readme_preview = None
        if self._readme_preview_uses_html:
            try:
                self.readme_preview_html = HtmlFrame(readme_frame)
                self.readme_preview_html.pack(fill=tk.BOTH, expand=True)
            except Exception:
                self._readme_preview_uses_html = False
                self.readme_preview_html = None
                self._build_text_readme_preview()
        else:
            self._build_text_readme_preview()

        self._build_settings_tab(settings_frame)

        self.status_var = tk.StringVar(value="")
        self.status_bar = ttk.Label(
            self, style="Astral.TLabel", textvariable=self.status_var, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.refresh_file_tree()
        self._apply_settings()
        self.refresh_readme_preview()

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _: self.new_file())
        self.bind("<Control-o>", lambda _: self.open_file())
        self.bind("<Control-s>", lambda _: self.save_file())
        self.bind("<Control-r>", lambda _: self.run_code())
        self.bind("<Control-Shift-F>",
                  lambda _: self.insert_astral_function_template())
        self.bind("<Control-Shift-L>",
                  lambda _: self.insert_astral_class_template())
        self.bind("<Control-Shift-K>", lambda _: self.check_astral_syntax())
        self.bind("<Control-Shift-T>", lambda _: self.insert_timestamp())
        self.bind("<Control-Shift-W>", lambda _: self.show_document_stats())
        self.bind("<Control-Shift-J>", lambda _: self.format_json_document())
        self.bind("<Control-Shift-M>", lambda _: self.show_readme_preview())

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _configure_editor_tags(self, font_size: int = 11, font_family: str | None = None) -> None:
        family = (font_family or self.font_family_var.get()
                  or "Consolas").strip()
        bold = (family, font_size, "bold")
        italic = (family, font_size, "italic")
        normal = (family, font_size)
        self.editor.tag_configure(
            "tok_number",      foreground="#B45309", font=normal)
        self.editor.tag_configure(
            "tok_operator",    foreground="#0EA5E9", font=normal)
        self.editor.tag_configure(
            "tok_literal",     foreground="#0F766E", font=bold)
        self.editor.tag_configure(
            "tok_builtin",     foreground="#9D174D", font=normal)
        self.editor.tag_configure(
            "tok_fn_call",     foreground="#0284C7", font=normal)
        self.editor.tag_configure(
            "tok_keyword",     foreground="#2563EB", font=bold)
        self.editor.tag_configure(
            "tok_fn_def",      foreground="#D97706", font=bold)
        self.editor.tag_configure(
            "tok_fstring",     foreground="#047857", font=normal)
        self.editor.tag_configure(
            "tok_fstring_brace", foreground="#FFFFFF", font=bold)
        self.editor.tag_configure(
            "tok_string",      foreground="#047857", font=normal)
        self.editor.tag_configure(
            "tok_comment",     foreground="#6B7280", font=italic)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(8, weight=1)

        ttk.Label(parent, style="Astral.TLabel", text="Editor Font Size").grid(
            row=0, column=0, sticky=tk.W, padx=12, pady=(14, 8))
        ttk.Spinbox(parent, style="Astral.TSpinbox", from_=9, to=24, textvariable=self.font_size_var, width=8).grid(
            row=0, column=1, sticky=tk.W, padx=12, pady=(14, 8)
        )

        ttk.Label(parent, style="Astral.TLabel", text="Editor Font Family").grid(
            row=1, column=0, sticky=tk.W, padx=12, pady=8)

        preferred_fonts = [
            "Consolas",
            "Cascadia Code",
            "JetBrains Mono",
            "Fira Code",
            "Courier New",
        ]
        try:
            available_fonts = sorted(set(tkfont.families(self)))
        except tk.TclError:
            available_fonts = preferred_fonts

        font_values: list[str] = []
        for name in preferred_fonts + available_fonts:
            if name not in font_values:
                font_values.append(name)

        if self.font_family_var.get() and self.font_family_var.get() not in font_values:
            font_values.insert(0, self.font_family_var.get())

        self._font_combo = ttk.Combobox(
            parent,
            style="Astral.TCombobox",
            textvariable=self.font_family_var,
            values=font_values,
            state="normal",
            width=22,
        )
        self._font_combo.grid(row=1, column=1, sticky=tk.W, padx=12, pady=8)

        ttk.Label(parent, style="Astral.TLabel", text="Theme").grid(
            row=2, column=0, sticky=tk.W, padx=12, pady=8)
        self._theme_combo = ttk.Combobox(
            parent,
            style="Astral.TCombobox",
            textvariable=self.theme_var,
            values=["Astral Light", "Astral Dark", "Solar Ember"],
            state="readonly",
            width=18,
        )
        self._theme_combo.grid(row=2, column=1, sticky=tk.W, padx=12, pady=8)

        ttk.Label(parent, style="Astral.TLabel", text="Editor Language").grid(
            row=3, column=0, sticky=tk.W, padx=12, pady=8)
        self._language_combo = ttk.Combobox(
            parent,
            style="Astral.TCombobox",
            textvariable=self.language_var,
            values=["Astral", "Python"],
            state="readonly",
            width=18,
        )
        self._language_combo.grid(
            row=3, column=1, sticky=tk.W, padx=12, pady=8)

        ttk.Checkbutton(
            parent,
            style="Astral.TCheckbutton",
            text="Enable autocomplete popup",
            variable=self.autocomplete_var,
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=12, pady=8)

        ttk.Checkbutton(
            parent,
            style="Astral.TCheckbutton",
            text="Autosave file before run",
            variable=self.autosave_on_run_var,
        ).grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=12, pady=8)

        ttk.Checkbutton(
            parent,
            style="Astral.TCheckbutton",
            text="Autosave when switching files",
            variable=self.autosave_on_switch_var,
        ).grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=12, pady=8)

        ttk.Button(parent, style="Astral.TButton", text="Apply Settings", command=self._apply_settings).grid(
            row=7, column=0, columnspan=2, sticky=tk.W, padx=12, pady=(14, 8)
        )

        ttk.Label(
            parent,
            style="Astral.TLabel",
            text=f"Version: {APP_VERSION}",
        ).grid(row=9, column=0, columnspan=2, sticky=tk.SW, padx=12, pady=(0, 12))

    def open_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Open Folder",
            initialdir=str(self.workspace_root or PROJECT_ROOT),
            mustexist=True,
        )
        if not selected:
            return

        self.workspace_root = Path(selected)
        self.refresh_file_tree()
        self.refresh_readme_preview()
        self._set_status(f"Opened folder {self.workspace_root}")

    def new_folder(self) -> None:
        root = self.workspace_root
        if root is None or not root.exists():
            messagebox.showerror(
                "No Workspace", "Open a workspace folder first.")
            return

        selected = self.file_tree.selection()
        target_dir = root
        if selected:
            selected_path = self._tree_paths.get(selected[0])
            if selected_path is not None:
                target_dir = selected_path if selected_path.is_dir() else selected_path.parent

        name = simpledialog.askstring(
            "New Folder",
            f"Folder name (inside {target_dir.name}):",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            self._set_status("New folder canceled")
            return
        if any(ch in name for ch in "\\/:*?\"<>|"):
            messagebox.showerror(
                "Invalid Name", "Folder name contains invalid characters.")
            return

        new_path = target_dir / name
        try:
            new_path.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            messagebox.showerror(
                "Exists", f"Folder already exists:\n{new_path}")
            return
        except OSError as exc:
            messagebox.showerror(
                "Create Failed", f"Could not create folder:\n{exc}")
            return

        self.refresh_file_tree()
        self._set_status(f"Created folder {new_path}")

    def refresh_file_tree(self) -> None:
        self._tree_paths.clear()
        self.file_tree.delete(*self.file_tree.get_children())

        root = self.workspace_root
        if root is None or not root.exists():
            self.workspace_label_var.set("Workspace: (none)")
            return

        self.workspace_label_var.set(f"Workspace: {root}")
        root_id = self.file_tree.insert("", tk.END, text=root.name, open=True)
        self._tree_paths[root_id] = root
        self._populate_tree_node(root_id, root)

    def _find_readme_path(self) -> Path | None:
        candidates: list[Path] = []

        if self.current_file is not None:
            candidates.append(self.current_file.parent / "README.md")

        if self.workspace_root is not None:
            candidates.append(self.workspace_root / "README.md")

        candidates.append(PROJECT_ROOT / "README.md")

        seen: set[Path] = set()
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if candidate.exists() and candidate.is_file():
                return candidate

        return None

    def _render_readme_preview(self, source: str, empty_placeholder: bool = True) -> str:
        lines: list[str] = []
        in_code_block = False

        for raw_line in source.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            if stripped.startswith("```"):
                in_code_block = not in_code_block
                if lines and lines[-1] != "":
                    lines.append("")
                continue

            if in_code_block:
                lines.append(f"    {line}")
                continue

            line = re.sub(
                r"!\[([^\]]*)\]\(([^\)]+)\)",
                lambda m: f"[Image: {(m.group(1) or Path(m.group(2)).name).strip()}]",
                line,
            )
            stripped = line.strip()

            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                if heading:
                    lines.append(heading.upper())
                    lines.append("=" * len(heading))
                    lines.append("")
                continue

            text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
            text = re.sub(r"`([^`]+)`", r"\1", text)

            if stripped.startswith(("- ", "* ")):
                bullet_text = stripped[2:].strip()
                bullet_text = re.sub(
                    r"\[([^\]]+)\]\([^\)]+\)", r"\1", bullet_text)
                bullet_text = re.sub(r"`([^`]+)`", r"\1", bullet_text)
                lines.append(f"• {bullet_text}")
                continue

            lines.append(text)

        rendered = "\n".join(lines).strip()
        if rendered:
            return rendered
        return "(README is empty)" if empty_placeholder else ""

    def _rewrite_markdown_targets_for_html(self, source: str, readme_path: Path) -> str:
        def _to_uri(target: str) -> str:
            cleaned = target.strip().strip('"').strip("'")
            if not cleaned or cleaned.startswith("#") or re.match(r"^[a-z]+://", cleaned, re.IGNORECASE):
                return cleaned
            candidate = Path(cleaned)
            if not candidate.is_absolute():
                candidate = readme_path.parent / candidate
            try:
                return candidate.resolve().as_uri()
            except OSError:
                return cleaned

        source = re.sub(
            r"!\[([^\]]*)\]\(([^\)]+)\)",
            lambda m: f"![{m.group(1)}]({_to_uri(m.group(2))})",
            source,
        )
        source = re.sub(
            r"(?<!!)\[([^\]]+)\]\(([^\)]+)\)",
            lambda m: f"[{m.group(1)}]({_to_uri(m.group(2))})",
            source,
        )
        return source

    def _render_readme_preview_html(self, source: str, readme_path: Path) -> str:
        themed_source = self._rewrite_markdown_targets_for_html(
            source, readme_path)
        body_html = markdown_to_html(
            themed_source,
            extensions=["fenced_code", "tables", "nl2br"],
        )
        bg = self._readme_preview_bg
        fg = self._readme_preview_fg
        return f"""
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\">
    <style>
        body {{
            background: {bg};
            color: {fg};
            font-family: Segoe UI, Arial, sans-serif;
            margin: 18px;
            line-height: 1.55;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1.2em;
            margin-bottom: 0.45em;
        }}
        code {{
            font-family: Consolas, monospace;
            background: rgba(127,127,127,0.16);
            padding: 2px 4px;
            border-radius: 4px;
        }}
        pre {{
            font-family: Consolas, monospace;
            background: rgba(127,127,127,0.16);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            border: 1px solid rgba(127,127,127,0.20);
        }}
        pre code {{
            background: transparent;
            padding: 0;
        }}
        a {{
            color: {fg};
        }}
        blockquote {{
            border-left: 4px solid rgba(127,127,127,0.35);
            margin-left: 0;
            padding-left: 12px;
            opacity: 0.92;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 14px 0;
            border: 1px solid rgba(127,127,127,0.20);
            border-radius: 6px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 12px 0;
        }}
        th, td {{
            border: 1px solid rgba(127,127,127,0.25);
            padding: 8px 10px;
            text-align: left;
        }}
        hr {{
            border: none;
            border-top: 1px solid rgba(127,127,127,0.25);
            margin: 20px 0;
        }}
    </style>
</head>
<body>
{body_html}
</body>
</html>
"""

    def _resolve_readme_image_path(self, image_target: str, readme_path: Path) -> Path | None:
        target = image_target.strip().strip('"').strip("'")
        if not target or re.match(r"^[a-z]+://", target, re.IGNORECASE):
            return None

        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = readme_path.parent / candidate

        return candidate if candidate.exists() and candidate.is_file() else None

    def _load_readme_preview_image(self, image_path: Path):
        if Image is None or ImageTk is None:
            return None

        try:
            image = Image.open(image_path)
            image.thumbnail((760, 420))
            photo = ImageTk.PhotoImage(image)
            self._readme_preview_images.append(photo)
            return photo
        except Exception:
            return None

    def _insert_readme_preview_content(self, source: str, readme_path: Path) -> None:
        self._readme_preview_images.clear()
        widget = self.readme_preview
        in_code_block = False

        for raw_line in source.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            if stripped.startswith("```"):
                in_code_block = not in_code_block
                if widget.index("end-1c") != "1.0":
                    widget.insert(tk.END, "\n")
                continue

            if not in_code_block:
                image_match = re.fullmatch(
                    r"!\[([^\]]*)\]\(([^\)]+)\)", stripped)
                if image_match:
                    alt_text = image_match.group(1).strip() or Path(
                        image_match.group(2)).name
                    image_path = self._resolve_readme_image_path(
                        image_match.group(2), readme_path)
                    photo = self._load_readme_preview_image(
                        image_path) if image_path else None
                    if photo is not None:
                        if widget.index("end-1c") != "1.0":
                            widget.insert(tk.END, "\n")
                        widget.image_create(tk.END, image=photo)
                        widget.insert(tk.END, f"\n[Image: {alt_text}]\n\n")
                    else:
                        fallback = alt_text
                        if image_path is not None:
                            fallback = f"{alt_text} ({image_path.name})"
                        widget.insert(tk.END, f"[Image: {fallback}]\n")
                    continue

            rendered = self._render_readme_preview(
                line, empty_placeholder=False)
            if rendered:
                widget.insert(tk.END, rendered + "\n")

    def _build_text_readme_preview(self) -> None:
        self.readme_preview = tk.Text(self._readme_frame, wrap=tk.WORD, font=(
            "Consolas", 10), state=tk.DISABLED)
        self.readme_preview.pack(fill=tk.BOTH, expand=True)

    def _fallback_to_text_readme_preview(self, reason: Exception | None = None) -> None:
        self._readme_preview_uses_html = False
        if self.readme_preview_html is not None:
            try:
                self.readme_preview_html.destroy()
            except Exception:
                pass
            self.readme_preview_html = None
        if self.readme_preview is None:
            self._build_text_readme_preview()
        self.readme_preview.configure(
            background=self._readme_preview_bg,
            foreground=self._readme_preview_fg,
            insertbackground=self._readme_preview_fg,
        )
        if reason is not None:
            self._set_status(
                f"README preview fell back to text mode: {reason}")

    def refresh_readme_preview(self, select_tab: bool = False) -> None:
        readme_path = self._find_readme_path()
        if self._readme_preview_uses_html and self.readme_preview_html is not None:
            try:
                if readme_path is None:
                    html = self._render_readme_preview_html(
                        "# README Preview\n\nNo README.md found for the current file or workspace.",
                        PROJECT_ROOT / "README.md",
                    )
                else:
                    try:
                        html = self._render_readme_preview_html(
                            readme_path.read_text(
                                encoding="utf-8"), readme_path
                        )
                    except OSError as exc:
                        html = self._render_readme_preview_html(
                            f"# README Preview\n\nCould not open README.md:\n\n```text\n{exc}\n```",
                            readme_path,
                        )
                self.readme_preview_html.load_html(html)
            except Exception as exc:
                self._fallback_to_text_readme_preview(exc)
                self.refresh_readme_preview(select_tab=False)
        else:
            if self.readme_preview is None:
                self._build_text_readme_preview()
            self.readme_preview.configure(state=tk.NORMAL)
            self.readme_preview.delete("1.0", tk.END)

            if readme_path is None:
                self._readme_preview_images.clear()
                self.readme_preview.insert(
                    "1.0", "No README.md found for the current file or workspace.")
            else:
                try:
                    self._insert_readme_preview_content(
                        readme_path.read_text(encoding="utf-8"), readme_path
                    )
                except OSError as exc:
                    self._readme_preview_images.clear()
                    self.readme_preview.insert(
                        "1.0", f"Could not open README.md:\n{exc}")

            self.readme_preview.configure(state=tk.DISABLED)

        if select_tab:
            self.notebook.select(2)
            self._set_status("README preview refreshed")

    def show_readme_preview(self) -> None:
        self.refresh_readme_preview(select_tab=True)

    def _populate_tree_node(self, parent_id: str, folder: Path) -> None:
        try:
            entries = sorted(folder.iterdir(), key=lambda p: (
                p.is_file(), p.name.lower()))
        except OSError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".astral_ide_settings.json"}:
                continue
            child_id = self.file_tree.insert(
                parent_id, tk.END, text=entry.name, open=False)
            self._tree_paths[child_id] = entry
            if entry.is_dir():
                self._populate_tree_node(child_id, entry)

    def _open_selected_tree_item(self, _event=None) -> None:
        selected = self.file_tree.selection()
        if not selected:
            return
        path = self._tree_paths.get(selected[0])
        if path is None or path.is_dir():
            return
        self._open_path_in_editor(path)

    def _open_path_in_editor(self, path: Path) -> None:
        if not self._confirm_discard_if_needed(switching_files=True):
            return
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Open Failed", f"Could not open file:\n{exc}")
            return

        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", content)
        self.current_file = path
        self._dirty = False
        self._refresh_title()
        self.refresh_readme_preview()
        self._set_status(f"Opened {path}")
        self._queue_highlight()

    def _load_settings(self) -> None:
        if not SETTINGS_PATH.exists():
            return

        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if isinstance(data, dict):
            font_size = data.get("font_size", 11)
            if isinstance(font_size, int):
                self.font_size_var.set(max(9, min(24, font_size)))

            font_family = data.get("font_family", "Consolas")
            if isinstance(font_family, str) and font_family.strip():
                self.font_family_var.set(font_family.strip())

            theme = data.get("theme", "Astral Light")
            if theme:  # accept any theme name; unknown ones fall back at render time
                self.theme_var.set(theme)

            language = data.get("language", "Astral")
            if language in {"Astral", "Python"}:
                self.language_var.set(language)

            autocomplete = data.get("autocomplete", True)
            if isinstance(autocomplete, bool):
                self.autocomplete_var.set(autocomplete)

            autosave_on_run = data.get("autosave_on_run", False)
            if isinstance(autosave_on_run, bool):
                self.autosave_on_run_var.set(autosave_on_run)

            autosave_on_switch = data.get("autosave_on_switch", False)
            if isinstance(autosave_on_switch, bool):
                self.autosave_on_switch_var.set(autosave_on_switch)

            workspace = data.get("workspace_root")
            if isinstance(workspace, str) and workspace:
                workspace_path = Path(workspace)
                if workspace_path.exists() and workspace_path.is_dir():
                    self.workspace_root = workspace_path

    def _save_settings(self) -> None:
        data = {
            "font_size": int(self.font_size_var.get()),
            "font_family": self.font_family_var.get().strip() or "Consolas",
            "theme": self.theme_var.get(),
            "language": self.language_var.get(),
            "autocomplete": bool(self.autocomplete_var.get()),
            "autosave_on_run": bool(self.autosave_on_run_var.get()),
            "autosave_on_switch": bool(self.autosave_on_switch_var.get()),
            "workspace_root": str(self.workspace_root) if self.workspace_root else "",
        }
        try:
            SETTINGS_PATH.write_text(json.dumps(
                data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _on_close(self) -> None:
        self._save_settings()
        self.destroy()

    def _apply_settings(self) -> None:
        font_size = max(9, min(24, int(self.font_size_var.get())))
        self.font_size_var.set(font_size)
        font_family = self.font_family_var.get().strip() or "Consolas"
        self.font_family_var.set(font_family)

        self.editor.configure(font=(font_family, font_size))
        self.output.configure(font=(font_family, max(9, font_size - 1)))

        if hasattr(self, "_font_combo"):
            current_values = list(self._font_combo.cget("values"))
            if font_family not in current_values:
                current_values.insert(0, font_family)
                self._font_combo.configure(values=current_values)

        themes = {
            "Astral Light": {
                "window_bg": "#F3F4F6", "panel_bg": "#E5E7EB", "panel_fg": "#111827",
                "tab_bg": "#D1D5DB", "tab_fg": "#111827",
                "tab_selected_bg": "#FFFFFF", "tab_selected_fg": "#0F172A",
                "editor_bg": "#FFFFFF", "editor_fg": "#111827",
                "output_bg": "#F9FAFB", "output_fg": "#111827",
                "readme_bg": "#F9FAFB", "readme_fg": "#111827",
                "keyword":      "#2563EB",
                "builtin":      "#9D174D",
                "literal":      "#0F766E",
                "number":       "#B45309",
                "operator":     "#0369A1",
                "string":       "#047857",
                "fstring":       "#047857",
                "fstring_brace": "#6B7280",
                "fn_def":        "#D97706",
                "fn_call":       "#0284C7",
                "comment":       "#6B7280",
            },
            "Astral Dark": {
                "window_bg": "#0B1220", "panel_bg": "#1E293B", "panel_fg": "#E5E7EB",
                "tab_bg": "#334155", "tab_fg": "#E5E7EB",
                "tab_selected_bg": "#0F172A", "tab_selected_fg": "#F8FAFC",
                "editor_bg": "#0F172A", "editor_fg": "#E5E7EB",
                "output_bg": "#111827", "output_fg": "#E5E7EB",
                "readme_bg": "#111827", "readme_fg": "#E5E7EB",
                "keyword":      "#60A5FA",
                "builtin":      "#F472B6",
                "literal":      "#2DD4BF",
                "number":       "#FB923C",
                "operator":     "#38BDF8",
                "string":       "#6EE7B7",
                "fstring":       "#6EE7B7",
                "fstring_brace": "#FFFFFF",
                "fn_def":        "#FCD34D",
                "fn_call":       "#93C5FD",
                "comment":       "#94A3B8",
            },
            "Solar Ember": {
                "window_bg": "#FFF1DD", "panel_bg": "#F4DCC5", "panel_fg": "#3A2E2A",
                "tab_bg": "#E7CDB1", "tab_fg": "#3A2E2A",
                "tab_selected_bg": "#FFF8ED", "tab_selected_fg": "#2F241F",
                "editor_bg": "#FFF8ED", "editor_fg": "#3A2E2A",
                "output_bg": "#FFF5E6", "output_fg": "#3A2E2A",
                "readme_bg": "#FFF5E6", "readme_fg": "#3A2E2A",
                "keyword":      "#1D4ED8",
                "builtin":      "#BE185D",
                "literal":      "#0D9488",
                "number":       "#C2410C",
                "operator":     "#0369A1",
                "string":       "#15803D",
                "fstring":       "#15803D",
                "fstring_brace": "#44322A",
                "fn_def":        "#B45309",
                "fn_call":       "#1D4ED8",
                "comment":       "#78716C",
            },
        }

        # Merge any custom themes saved by astral_theme_maker
        # Check multiple locations for backwards compatibility with exe packaging
        _home_themes = Path.home() / ".astral_custom_themes.json"
        _fallback_locations = [
            _home_themes,
            PROJECT_ROOT / ".astral_custom_themes.json",
            Path.cwd() / ".astral_custom_themes.json",
        ]

        _custom_file = None
        for loc in _fallback_locations:
            if loc.exists():
                _custom_file = loc
                break

        # If found in fallback location, migrate to home directory
        if _custom_file and _custom_file != _home_themes:
            try:
                _home_themes.write_text(_custom_file.read_text(
                    encoding="utf-8"), encoding="utf-8")
                _custom_file = _home_themes
            except Exception:
                pass

        # Load custom themes from home directory
        if _custom_file and _custom_file.exists():
            try:
                _extra = json.loads(_custom_file.read_text(encoding="utf-8"))
                if isinstance(_extra, dict):
                    themes.update(_extra)
            except Exception:
                pass

        # Refresh the theme combobox so new names appear
        if hasattr(self, "_theme_combo"):
            self._theme_combo.configure(values=list(themes))

        chosen = themes.get(self.theme_var.get(), themes["Astral Light"])
        self.configure(background=chosen["window_bg"])

        self.style.configure("Astral.TFrame", background=chosen["window_bg"])
        self.style.configure(
            "Astral.TLabel", background=chosen["panel_bg"], foreground=chosen["panel_fg"])
        self.style.configure(
            "Astral.TButton", background=chosen["panel_bg"], foreground=chosen["panel_fg"])
        self.style.configure(
            "Astral.TCheckbutton", background=chosen["window_bg"], foreground=chosen["panel_fg"])
        self.style.configure("Astral.TNotebook",
                             background=chosen["window_bg"], borderwidth=0)
        self.style.configure(
            "Astral.TNotebook.Tab",
            background=chosen["tab_bg"],
            foreground=chosen["tab_fg"],
            padding=(12, 6),
        )
        self.style.map(
            "Astral.TNotebook.Tab",
            background=[
                ("selected", chosen["tab_selected_bg"]),
                ("active", chosen["tab_bg"]),
                ("!selected", chosen["tab_bg"]),
            ],
            foreground=[
                ("selected", chosen["tab_selected_fg"]),
                ("active", chosen["tab_fg"]),
                ("!selected", chosen["tab_fg"]),
            ],
        )
        self.style.configure(
            "Astral.TCombobox",
            fieldbackground=chosen["editor_bg"],
            background=chosen["panel_bg"],
            foreground=chosen["editor_fg"],
            arrowcolor=chosen["editor_fg"],
            selectbackground=chosen["tab_bg"],
            selectforeground=chosen["tab_fg"],
        )
        self.style.map(
            "Astral.TCombobox",
            fieldbackground=[
                ("readonly", chosen["editor_bg"]),
                ("!readonly", chosen["editor_bg"]),
            ],
            background=[
                ("readonly", chosen["panel_bg"]),
                ("!readonly", chosen["panel_bg"]),
            ],
            foreground=[
                ("readonly", chosen["editor_fg"]),
                ("!readonly", chosen["editor_fg"]),
            ],
            arrowcolor=[
                ("readonly", chosen["editor_fg"]),
                ("!readonly", chosen["editor_fg"]),
            ],
        )
        # Popdown listbox colors for comboboxes (theme and language selectors).
        self.option_add("*TCombobox*Listbox*Background", chosen["editor_bg"])
        self.option_add("*TCombobox*Listbox*Foreground", chosen["editor_fg"])
        self.option_add("*TCombobox*Listbox*selectBackground",
                        chosen["tab_bg"])
        self.option_add("*TCombobox*Listbox*selectForeground",
                        chosen["tab_fg"])
        self.style.configure(
            "Astral.TSpinbox", fieldbackground=chosen["editor_bg"], foreground=chosen["editor_fg"])
        self.style.configure(
            "Astral.Treeview",
            fieldbackground=chosen["editor_bg"],
            background=chosen["editor_bg"],
            foreground=chosen["editor_fg"],
        )
        self.style.map(
            "Astral.Treeview",
            background=[("selected", chosen["tab_bg"])],
            foreground=[("selected", chosen["tab_fg"])],
        )

        if hasattr(self, "status_bar"):
            self.status_bar.configure(style="Astral.TLabel")

        self.editor.configure(
            background=chosen["editor_bg"],
            foreground=chosen["editor_fg"],
            insertbackground=chosen["editor_fg"],
        )
        self.output.configure(
            background=chosen["output_bg"],
            foreground=chosen["output_fg"],
            insertbackground=chosen["output_fg"],
        )
        self._readme_preview_bg = chosen.get("readme_bg", chosen["output_bg"])
        self._readme_preview_fg = chosen.get("readme_fg", chosen["output_fg"])
        if not self._readme_preview_uses_html:
            self.readme_preview.configure(
                background=self._readme_preview_bg,
                foreground=self._readme_preview_fg,
                insertbackground=self._readme_preview_fg,
            )
        self.refresh_readme_preview()

        fs = max(9, min(24, int(self.font_size_var.get())))
        bold = (font_family, fs, "bold")
        italic = (font_family, fs, "italic")
        normal = (font_family, fs)
        self.editor.tag_configure(
            "tok_number",       foreground=chosen["number"],      font=normal)
        self.editor.tag_configure(
            "tok_operator",     foreground=chosen["operator"],    font=normal)
        self.editor.tag_configure(
            "tok_literal",      foreground=chosen["literal"],     font=bold)
        self.editor.tag_configure(
            "tok_builtin",      foreground=chosen["builtin"],     font=normal)
        self.editor.tag_configure(
            "tok_fn_call",      foreground=chosen["fn_call"],     font=normal)
        self.editor.tag_configure(
            "tok_keyword",      foreground=chosen["keyword"],     font=bold)
        self.editor.tag_configure(
            "tok_fn_def",       foreground=chosen["fn_def"],      font=bold)
        self.editor.tag_configure(
            "tok_fstring",      foreground=chosen["fstring"],     font=normal)
        self.editor.tag_configure(
            "tok_fstring_brace", foreground=chosen["fstring_brace"], font=bold)
        self.editor.tag_configure(
            "tok_string",       foreground=chosen["string"],      font=normal)
        self.editor.tag_configure(
            "tok_comment",      foreground=chosen["comment"],     font=italic)

        self.file_tree.configure(style="Astral.Treeview")
        self._save_settings()
        self._queue_highlight()
        self._refresh_title()
        self._set_status("Settings applied")

    def _queue_highlight(self) -> None:
        if self._highlight_job is not None:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(60, self._apply_syntax_highlighting)

    def _on_key_release(self, _event) -> None:
        self._queue_highlight()
        self._update_autocomplete()

    def _collect_identifiers(self) -> set[str]:
        text = self.editor.get("1.0", tk.END)
        found = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text))
        keywords, builtins_set, literals = self._language_tokens()
        return found - keywords - builtins_set - literals

    def _language_tokens(self) -> tuple[set[str], set[str], set[str]]:
        if self.language_var.get() == "Python":
            return PY_KEYWORDS, PY_BUILTINS, PY_LITERALS
        return KEYWORDS, BUILTINS, LITERALS

    def _current_word_prefix(self) -> tuple[str, str] | None:
        cursor = self.editor.index("insert")
        line_start = f"{cursor} linestart"
        before = self.editor.get(line_start, cursor)
        match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", before)
        if not match:
            return None
        prefix = match.group(1)
        start = f"{cursor}-{len(prefix)}c"
        return prefix, start

    def _update_autocomplete(self) -> None:
        if not self.autocomplete_var.get():
            self._close_autocomplete()
            return

        result = self._current_word_prefix()
        if result is None:
            self._close_autocomplete()
            return

        prefix, start = result
        keywords, builtins_set, literals = self._language_tokens()
        suggestions = sorted(
            [
                token
                for token in (keywords | builtins_set | literals | self._collect_identifiers())
                if token.startswith(prefix) and token != prefix
            ]
        )

        if not suggestions:
            self._close_autocomplete()
            return

        self._show_autocomplete(start, suggestions)

    def _show_autocomplete(self, start: str, suggestions: list[str]) -> None:
        if self._autocomplete_window is None:
            self._autocomplete_window = tk.Toplevel(self)
            self._autocomplete_window.wm_overrideredirect(True)
            self._autocomplete_window.attributes("-topmost", True)
            self._autocomplete_listbox = tk.Listbox(
                self._autocomplete_window,
                height=8,
                width=24,
                font=("Consolas", 10),
            )
            self._autocomplete_listbox.pack(fill=tk.BOTH, expand=True)
            self._autocomplete_listbox.bind(
                "<Double-Button-1>", self._accept_autocomplete)

        assert self._autocomplete_listbox is not None
        self._autocomplete_start = start
        self._autocomplete_listbox.delete(0, tk.END)
        for item in suggestions:
            self._autocomplete_listbox.insert(tk.END, item)
        self._autocomplete_listbox.selection_clear(0, tk.END)
        self._autocomplete_listbox.selection_set(0)
        self._autocomplete_listbox.activate(0)

        bbox = self.editor.bbox("insert")
        if bbox is None:
            self._close_autocomplete()
            return
        x, y, width, height = bbox
        root_x = self.editor.winfo_rootx() + x
        root_y = self.editor.winfo_rooty() + y + height
        self._autocomplete_window.geometry(f"+{root_x}+{root_y}")
        self._autocomplete_window.deiconify()

    def _autocomplete_open(self) -> bool:
        return (
            self._autocomplete_window is not None
            and self._autocomplete_listbox is not None
            and self._autocomplete_window.winfo_exists()
        )

    def _trigger_autocomplete(self, _event=None):
        if not self.autocomplete_var.get():
            return "break"
        self._update_autocomplete()
        return "break"

    def _accept_autocomplete(self, _event=None):
        if not self._autocomplete_open() or self._autocomplete_start is None:
            return None

        assert self._autocomplete_listbox is not None
        selected = self._autocomplete_listbox.curselection()
        if not selected:
            return "break"

        choice = self._autocomplete_listbox.get(selected[0])
        self.editor.delete(self._autocomplete_start, "insert")
        self.editor.insert("insert", choice)
        self._close_autocomplete()
        return "break"

    def _close_autocomplete(self, _event=None):
        if self._autocomplete_window is not None and self._autocomplete_window.winfo_exists():
            self._autocomplete_window.withdraw()
        self._autocomplete_start = None
        return None

    def _autocomplete_prev(self, _event=None):
        if not self._autocomplete_open():
            return None
        assert self._autocomplete_listbox is not None
        selected = self._autocomplete_listbox.curselection()
        index = selected[0] if selected else 0
        index = max(index - 1, 0)
        self._autocomplete_listbox.selection_clear(0, tk.END)
        self._autocomplete_listbox.selection_set(index)
        self._autocomplete_listbox.activate(index)
        return "break"

    def _autocomplete_next(self, _event=None):
        if not self._autocomplete_open():
            return None
        assert self._autocomplete_listbox is not None
        selected = self._autocomplete_listbox.curselection()
        index = selected[0] if selected else 0
        last = max(self._autocomplete_listbox.size() - 1, 0)
        index = min(index + 1, last)
        self._autocomplete_listbox.selection_clear(0, tk.END)
        self._autocomplete_listbox.selection_set(index)
        self._autocomplete_listbox.activate(index)
        return "break"

    def _apply_syntax_highlighting(self) -> None:
        self._highlight_job = None
        text = self.editor.get("1.0", tk.END)

        if self.language_var.get() == "Python":
            self._apply_python_syntax_highlighting(text)
            return

        all_tags = [
            "tok_number", "tok_operator", "tok_literal", "tok_builtin",
            "tok_fn_call", "tok_keyword", "tok_fn_def",
            "tok_fstring", "tok_string", "tok_comment", "tok_fstring_brace",
        ]
        for tag in all_tags:
            self.editor.tag_remove(tag, "1.0", tk.END)

        # Numbers
        self._highlight_pattern(r"\b\d+(?:\.\d+)?\b", "tok_number", text)

        # Operators
        self._highlight_pattern(
            r"(?:==|!=|<=|>=|[+\-*/%<>!])", "tok_operator", text)

        # Literals, builtins, keywords
        for token in sorted(LITERALS):
            self._highlight_pattern(
                rf"\b{re.escape(token)}\b", "tok_literal", text)
        for token in sorted(BUILTINS):
            self._highlight_pattern(
                rf"\b{re.escape(token)}\b", "tok_builtin", text)
        for token in sorted(KEYWORDS):
            self._highlight_pattern(
                rf"\b{re.escape(token)}\b", "tok_keyword", text)

        # Function calls: identifier immediately before (
        self._highlight_pattern(
            r"\b([A-Za-z_]\w*)(?=\s*\()", "tok_fn_call", text)

        # Function definitions: name after fn keyword
        self._highlight_group_pattern(
            r"\bfn\s+([A-Za-z_]\w*)", 1, "tok_fn_def", text)

        # Strings and f-strings are found by scanning so closing quotes do not
        # get misdetected as a new string start.
        string_spans = self._find_string_spans(text)

        for start, end, is_fstring in string_spans:
            if not is_fstring:
                self.editor.tag_add(
                    "tok_string", f"1.0+{start}c", f"1.0+{end}c")

        # F-strings: color literal parts as fstring, leave {expr} for normal tags,
        # then paint just the { } brace characters so they stand out.
        for fstart, fend, is_fstring in string_spans:
            if not is_fstring:
                continue
            ftext = text[fstart:fend]
            fbase = fstart
            expr_spans = [(m.start(), m.end())
                          for m in re.finditer(r"\{[^}]*\}", ftext)]
            # Paint the literal (non-expression) segments
            prev = 0
            for es, ee in expr_spans:
                if prev < es:
                    self.editor.tag_add(
                        "tok_fstring",
                        f"1.0+{fbase + prev}c",
                        f"1.0+{fbase + es}c",
                    )
                prev = ee
            if prev < len(ftext):
                self.editor.tag_add(
                    "tok_fstring",
                    f"1.0+{fbase + prev}c",
                    f"1.0+{fbase + len(ftext)}c",
                )
            # Paint just the brace characters
            for es, ee in expr_spans:
                self.editor.tag_add(
                    "tok_fstring_brace",
                    f"1.0+{fbase + es}c",
                    f"1.0+{fbase + es + 1}c",
                )
                self.editor.tag_add(
                    "tok_fstring_brace",
                    f"1.0+{fbase + ee - 1}c",
                    f"1.0+{fbase + ee}c",
                )

        # Comments last — highest priority
        self._highlight_pattern(r"//.*$", "tok_comment",
                                text, flags=re.MULTILINE)

        # Enforce tag priority (raise = wins over all previously raised)
        for tag in all_tags:
            self.editor.tag_raise(tag)

    def _apply_python_syntax_highlighting(self, text: str) -> None:
        all_tags = [
            "tok_number", "tok_operator", "tok_literal", "tok_builtin",
            "tok_fn_call", "tok_keyword", "tok_fn_def",
            "tok_fstring", "tok_string", "tok_comment", "tok_fstring_brace",
        ]
        for tag in all_tags:
            self.editor.tag_remove(tag, "1.0", tk.END)

        self._highlight_pattern(r"\b\d+(?:\.\d+)?\b", "tok_number", text)
        self._highlight_pattern(
            r"(?:==|!=|<=|>=|\+=|-=|\*=|/=|//=|%=|\*\*|[+\-*/%<>!=])", "tok_operator", text)

        for token in sorted(PY_LITERALS):
            self._highlight_pattern(
                rf"\b{re.escape(token)}\b", "tok_literal", text)
        for token in sorted(PY_BUILTINS):
            self._highlight_pattern(
                rf"\b{re.escape(token)}\b", "tok_builtin", text)
        for token in sorted(PY_KEYWORDS):
            self._highlight_pattern(
                rf"\b{re.escape(token)}\b", "tok_keyword", text)

        self._highlight_pattern(
            r"\b([A-Za-z_]\w*)(?=\s*\()", "tok_fn_call", text)
        self._highlight_group_pattern(
            r"\bdef\s+([A-Za-z_]\w*)", 1, "tok_fn_def", text)

        string_spans = self._find_string_spans(text)
        for start, end, is_fstring in string_spans:
            if not is_fstring:
                self.editor.tag_add(
                    "tok_string", f"1.0+{start}c", f"1.0+{end}c")

        for fstart, fend, is_fstring in string_spans:
            if not is_fstring:
                continue
            ftext = text[fstart:fend]
            fbase = fstart
            expr_spans = [(m.start(), m.end())
                          for m in re.finditer(r"\{[^}]*\}", ftext)]
            prev = 0
            for es, ee in expr_spans:
                if prev < es:
                    self.editor.tag_add(
                        "tok_fstring", f"1.0+{fbase + prev}c", f"1.0+{fbase + es}c")
                prev = ee
            if prev < len(ftext):
                self.editor.tag_add(
                    "tok_fstring", f"1.0+{fbase + prev}c", f"1.0+{fbase + len(ftext)}c")
            for es, ee in expr_spans:
                self.editor.tag_add(
                    "tok_fstring_brace", f"1.0+{fbase + es}c", f"1.0+{fbase + es + 1}c")
                self.editor.tag_add(
                    "tok_fstring_brace", f"1.0+{fbase + ee - 1}c", f"1.0+{fbase + ee}c")

        self._highlight_pattern(r"#.*$", "tok_comment",
                                text, flags=re.MULTILINE)

        for tag in all_tags:
            self.editor.tag_raise(tag)

    def _highlight_pattern(self, pattern: str, tag: str, text: str, flags: int = 0) -> None:
        for match in re.finditer(pattern, text, flags):
            self.editor.tag_add(
                tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")

    def _highlight_group_pattern(self, pattern: str, group: int, tag: str, text: str) -> None:
        for match in re.finditer(pattern, text):
            self.editor.tag_add(
                tag, f"1.0+{match.start(group)}c", f"1.0+{match.end(group)}c")

    def _find_string_spans(self, text: str) -> list[tuple[int, int, bool]]:
        spans: list[tuple[int, int, bool]] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] not in {'"', "'"}:
                i += 1
                continue

            quote_char = text[i]
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
                elif ch == quote_char:
                    j += 1
                    break
                j += 1

            spans.append((span_start, min(j, n), is_fstring))
            i = max(j, i + 1)

        return spans

    def _on_modified(self, _event) -> None:
        if self.editor.edit_modified():
            self._dirty = True
            self.editor.edit_modified(False)
            self._refresh_title()
            self._queue_highlight()

    def _refresh_title(self) -> None:
        if self.current_file:
            base = self.current_file.name
        else:
            default_name = "Untitled.py" if self.language_var.get() == "Python" else "Untitled.ast"
            base = default_name
        mark = "*" if self._dirty else ""
        self.title(f"Astral IDE [{self.language_var.get()}] - {base}{mark}")

    def _confirm_discard_if_needed(self, switching_files: bool = False) -> bool:
        if not self._dirty:
            return True

        if switching_files and self.autosave_on_switch_var.get():
            return self.save_file()

        answer = messagebox.askyesnocancel(
            "Unsaved Changes", "Save changes before continuing?")
        if answer is None:
            return False
        if answer:
            return self.save_file()
        return True

    def new_file(self) -> None:
        if not self._confirm_discard_if_needed():
            return
        self.editor.delete("1.0", tk.END)
        self.current_file = None
        self._dirty = False
        self._refresh_title()
        self._set_status("New file")
        self._queue_highlight()

    def open_file(self) -> None:
        if not self._confirm_discard_if_needed(switching_files=True):
            return

        file_path = filedialog.askopenfilename(
            title=f"Open {self.language_var.get()} File",
            defaultextension=".py" if self.language_var.get() == "Python" else ".ast",
            filetypes=[("Python Files", "*.py"), ("Astral Files", "*.ast"),
                       ("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=self.workspace_root or PROJECT_ROOT,
        )
        if not file_path:
            return

        self._open_path_in_editor(Path(file_path))

    def save_file(self) -> bool:
        target = self.current_file
        if target is None:
            file_path = filedialog.asksaveasfilename(
                title=f"Save {self.language_var.get()} File",
                defaultextension=".py" if self.language_var.get() == "Python" else ".ast",
                filetypes=[("Python Files", "*.py"), ("Astral Files", "*.ast"),
                           ("Text Files", "*.txt"), ("All Files", "*.*")],
                initialdir=self.workspace_root or PROJECT_ROOT,
            )
            if not file_path:
                return False
            target = Path(file_path)

        source = self.editor.get("1.0", tk.END)
        target.write_text(source, encoding="utf-8")
        self.current_file = target
        self._dirty = False
        self._refresh_title()
        self.refresh_file_tree()
        self.refresh_readme_preview()
        self._set_status(f"Saved {target}")
        return True

    # IDE-only utility: inserts current timestamp at the cursor.
    def insert_timestamp(self) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.editor.insert("insert", stamp)
        self.editor.edit_modified(True)
        self._on_modified(None)
        self._set_status("Inserted timestamp")

    # IDE-only utility: computes basic document statistics.
    def show_document_stats(self) -> None:
        text = self.editor.get("1.0", "end-1c")
        chars = len(text)
        lines = text.count("\n") + (1 if text else 0)
        words = len(re.findall(r"\S+", text))
        message = f"Lines: {lines}\nWords: {words}\nCharacters: {chars}"
        self._write_output(message)
        self.notebook.select(1)
        self._set_status("Document stats generated")

    # IDE-only utility: pretty-prints JSON currently in the editor.
    def format_json_document(self) -> None:
        source = self.editor.get("1.0", "end-1c")
        if not source.strip():
            self._set_status("Format JSON canceled: empty document")
            return
        try:
            parsed = json.loads(source)
        except json.JSONDecodeError as exc:
            self._write_output(f"JSON format error: {exc}")
            self.notebook.select(1)
            self._set_status("Format JSON failed")
            return

        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", formatted)
        self.editor.edit_modified(True)
        self._on_modified(None)
        self._queue_highlight()
        self._set_status("JSON formatted")

    # IDE-only utility: inserts an Astral function template.
    def insert_astral_function_template(self) -> None:
        template = (
            "fn my_function(value) {\n"
            "  print value\n"
            "  return value\n"
            "}\n"
        )
        self.editor.insert("insert", template)
        self.editor.edit_modified(True)
        self._on_modified(None)
        self._queue_highlight()
        self._set_status("Inserted Astral function template")

    # IDE-only utility: inserts an Astral class template.
    def insert_astral_class_template(self) -> None:
        template = (
            "class MyClass {\n"
            "  fn init(name) {\n"
            "    this.name = name\n"
            "  }\n"
            "\n"
            "  fn greet() {\n"
            "    print f\"Hello {this.name}\"\n"
            "  }\n"
            "}\n"
        )
        self.editor.insert("insert", template)
        self.editor.edit_modified(True)
        self._on_modified(None)
        self._queue_highlight()
        self._set_status("Inserted Astral class template")

    # IDE-only utility: parses current Astral source and reports syntax issues without running code.
    def check_astral_syntax(self) -> None:
        if self.language_var.get() == "Python":
            self._set_status("Check Astral skipped: language is Python")
            return

        source = self.editor.get("1.0", "end-1c")
        if not source.strip():
            self._set_status("Check Astral canceled: empty document")
            return

        try:
            tokens = Lexer(source).scan_tokens()
            Parser(tokens).parse()
        except ParseError as exc:
            self._write_output(
                f"Astral syntax error:\n{exc.format_with_source(source)}")
            self.notebook.select(1)
            self._set_status("Astral syntax check failed")
            return
        except LexerError as exc:
            self._write_output(f"Astral syntax error: {exc}")
            self.notebook.select(1)
            self._set_status("Astral syntax check failed")
            return

        self._write_output("Astral syntax check passed.")
        self.notebook.select(1)
        self._set_status("Astral syntax check passed")

    def _write_output(self, text: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text.rstrip() + "\n")
        self.output.configure(state=tk.DISABLED)

    def _ide_input(self, prompt: str = "") -> str:
        response = simpledialog.askstring(
            "Astral Input",
            prompt if prompt else "Input:",
            parent=self,
        )
        if response is None:
            raise RuntimeErrorPebble("Input canceled by user.")
        return response

    def _run_description_file_if_applicable(self, source: str) -> bool:
        text = source.strip()
        if not text:
            if self.current_file and self.current_file.name.lower() in {"deci.ast", "desc.ast", "description.ast"}:
                self._write_output("(No description)")
                self._set_status("Description file is empty")
                return True
            return False

        description_names = {"deci.ast", "desc.ast", "description.ast"}
        name_match = bool(
            self.current_file
            and self.current_file.suffix.lower() == ".ast"
            and self.current_file.name.lower() in description_names
        )
        json_like = text.startswith("{") and (
            '"description"' in text or '"decription"' in text
        )

        description = self._extract_description_from_source(source)

        if not name_match and not json_like and description is None:
            return False

        if not description:
            # Fallback for slightly-invalid JSON that still clearly contains a description field.
            m = re.search(
                r'"(?:description|decription)"\s*:\s*"((?:\\.|[^"\\])*)"',
                text,
            )
            if m:
                raw = m.group(1)
                description = bytes(
                    raw, "utf-8").decode("unicode_escape").strip()

        if not description:
            for line in source.splitlines():
                stripped = line.strip()
                if stripped:
                    description = stripped
                    break

        self._write_output(description if description else "(No description)")
        self._set_status("Description printed")
        return True

    def _extract_description_from_source(self, source: str) -> str | None:
        text = source.strip()
        if not text:
            return None

        # Handle UTF-8 BOM so JSON files saved by some editors still parse.
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None

        fields: dict[str, str] = {}

        if isinstance(data, dict):
            name_value = data.get("name")
            if isinstance(name_value, str) and name_value.strip():
                fields["name"] = name_value.strip()

            version_value = data.get("version")
            if version_value is None:
                version_value = data.get("verion")
            if isinstance(version_value, (str, int, float)):
                version_text = str(version_value).strip()
                if version_text:
                    fields["version"] = version_text

            desc_value = data.get("description")
            if not isinstance(desc_value, str):
                # Common typo support.
                desc_value = data.get("decription")
            if isinstance(desc_value, str):
                cleaned = desc_value.strip()
                if cleaned:
                    fields["description"] = cleaned

        if not fields:
            # Fallback for slightly-invalid JSON that still contains recognizable keys.
            name_match = re.search(
                r'"name"\s*:\s*"((?:\\.|[^"\\])*)"', text)
            if name_match:
                fields["name"] = bytes(name_match.group(
                    1), "utf-8").decode("unicode_escape").strip()

            version_match = re.search(
                r'"(?:version|verion)"\s*:\s*("((?:\\.|[^"\\])*)"|[-+]?[0-9]+(?:\.[0-9]+)*)',
                text,
            )
            if version_match:
                if version_match.group(2) is not None:
                    fields["version"] = bytes(version_match.group(
                        2), "utf-8").decode("unicode_escape").strip()
                else:
                    fields["version"] = version_match.group(1).strip()

            desc_match = re.search(
                r'"(?:description|decription)"\s*:\s*"((?:\\.|[^"\\])*)"',
                text,
            )
            if desc_match:
                fields["description"] = bytes(desc_match.group(
                    1), "utf-8").decode("unicode_escape").strip()

        lines: list[str] = []
        if fields.get("name"):
            lines.append(f"Name: {fields['name']}")
        if fields.get("version"):
            lines.append(f"Version: {fields['version']}")
        if fields.get("description"):
            lines.append(f"Description: {fields['description']}")

        if lines:
            return "\n".join(lines)

        return None

    def _extract_description_fallback(self, source: str) -> str:
        description = self._extract_description_from_source(source)
        if description is not None:
            return description
        for line in source.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return "(No description)"

    def _looks_like_description_source(self, source: str) -> bool:
        stripped = source.lstrip("\ufeff \t\r\n")
        if stripped.startswith("{") and (
            '"description"' in stripped
            or '"decription"' in stripped
            or '"name"' in stripped
            or '"version"' in stripped
            or '"verion"' in stripped
        ):
            return True
        return False

    def run_code(self) -> None:
        if self.autosave_on_run_var.get() and self._dirty:
            if not self.save_file():
                self._set_status("Run canceled")
                return

        source = self.editor.get("1.0", tk.END)
        if not source.strip():
            self._write_output("Nothing to run.")
            self._set_status("No code to run")
            return

        # Fail-safe: JSON-like files should not be sent through the Astral lexer.
        stripped = source.lstrip("\ufeff \t\r\n")
        if self.language_var.get() != "Python" and stripped.startswith("{"):
            self._write_output(self._extract_description_fallback(source))
            self._set_status("Description printed")
            return

        if self._run_description_file_if_applicable(source):
            return

        try:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                with patch("builtins.input", self._ide_input):
                    if self.language_var.get() == "Python":
                        globals_dict = {"__name__": "__main__",
                                        "__builtins__": py_builtins}
                        exec(
                            compile(source, str(self.current_file or "<editor>"), "exec"), globals_dict)
                    else:
                        tokens = Lexer(source).scan_tokens()
                        statements = Parser(tokens).parse()
                        Interpreter().interpret(statements)
            output_text = buffer.getvalue().rstrip()
            self._write_output(
                output_text if output_text else "(Program produced no output)")
            self._set_status("Run complete")
        except ParseError as exc:
            if self._looks_like_description_source(source):
                self._write_output(self._extract_description_fallback(source))
                self._set_status("Description printed")
                return
            if self.current_file and self.current_file.name.lower() in {"deci.ast", "desc.ast", "description.ast"}:
                description = self._extract_description_from_source(source)
                if description is not None:
                    self._write_output(description)
                    self._set_status("Description printed")
                    return
            self._write_output(
                f"Astral error: {exc.format_with_source(source)}")
            self._set_status("Parse error")
        except (LexerError, RuntimeErrorPebble) as exc:
            if self._looks_like_description_source(source):
                self._write_output(self._extract_description_fallback(source))
                self._set_status("Description printed")
                return
            if self.current_file and self.current_file.name.lower() in {"deci.ast", "desc.ast", "description.ast"}:
                description = self._extract_description_from_source(source)
                if description is not None:
                    self._write_output(description)
                    self._set_status("Description printed")
                    return
            self._write_output(f"Astral error: {exc}")
            self._set_status("Runtime error")
        except Exception:
            self._write_output(traceback.format_exc())
            self._set_status("Python error")
        except EOFError:
            self._write_output(
                "Astral error: input is not available in this context.")
            self._set_status("Runtime error")


def main() -> None:
    app = AstralIDE()
    app.mainloop()


if __name__ == "__main__":
    main()

