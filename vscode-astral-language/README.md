# Astral Language Support for VS Code

This extension adds basic language support for Astral (`.ast`) files:

- File association for `.ast`
- Syntax highlighting
- Comment and bracket configuration
- Starter snippets
- Auto-complete for keywords, built-ins, functions, and variables
- Live diagnostics for common syntax issues

## Local usage (without publishing)

1. Open this folder in VS Code:
   - `python_projects/pebble_lang/vscode-astral-language`
2. Press `F5` to launch an Extension Development Host.
3. In the new window, open any `.ast` file.
4. Confirm language mode shows `Astral`.

## Diagnostics included

- Unmatched or unclosed `{}` and `()`
- Unterminated string literals
- `let` declarations missing `=`
- `fn` declarations missing `(`
- `return` outside function blocks (warning)

## Notes

- This extension now provides lightweight autocomplete + diagnostics without an LSP.
- You can later upgrade to a full language server for deeper semantic checks.
