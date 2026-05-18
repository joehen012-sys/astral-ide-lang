const vscode = require("vscode");

const KEYWORDS = ["fn", "return", "let", "if", "elif", "else", "while", "class", "import", "this", "and", "or", "not"];
const BUILTINS = ["print", "input", "len"];
const LITERALS = ["true", "false", "nil"];

function activate(context) {
  const diagnostics = vscode.languages.createDiagnosticCollection("astral");
  context.subscriptions.push(diagnostics);

  const completionProvider = vscode.languages.registerCompletionItemProvider(
    { language: "astral", scheme: "file" },
    {
      provideCompletionItems(document) {
        const items = [];

        for (const keyword of KEYWORDS) {
          const item = new vscode.CompletionItem(keyword, vscode.CompletionItemKind.Keyword);
          item.insertText = keyword;
          items.push(item);
        }

        for (const builtin of BUILTINS) {
          const item = new vscode.CompletionItem(builtin, vscode.CompletionItemKind.Function);
          item.insertText = builtin;
          items.push(item);
        }

        for (const literal of LITERALS) {
          const item = new vscode.CompletionItem(literal, vscode.CompletionItemKind.Constant);
          item.insertText = literal;
          items.push(item);
        }

        const symbols = collectDocumentSymbols(document.getText());
        for (const fnName of symbols.functions) {
          const item = new vscode.CompletionItem(fnName, vscode.CompletionItemKind.Function);
          item.insertText = fnName;
          items.push(item);
        }

        for (const varName of symbols.variables) {
          const item = new vscode.CompletionItem(varName, vscode.CompletionItemKind.Variable);
          item.insertText = varName;
          items.push(item);
        }

        return items;
      },
    },
    "_"
  );
  context.subscriptions.push(completionProvider);

  const refreshDiagnostics = (doc) => {
    if (doc.languageId !== "astral") {
      return;
    }
    diagnostics.set(doc.uri, buildDiagnostics(doc));
  };

  if (vscode.window.activeTextEditor) {
    refreshDiagnostics(vscode.window.activeTextEditor.document);
  }

  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(refreshDiagnostics),
    vscode.workspace.onDidChangeTextDocument((event) => refreshDiagnostics(event.document)),
    vscode.workspace.onDidSaveTextDocument(refreshDiagnostics),
    vscode.workspace.onDidCloseTextDocument((doc) => diagnostics.delete(doc.uri)),
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        refreshDiagnostics(editor.document);
      }
    })
  );
}

function deactivate() {}

function collectDocumentSymbols(source) {
  const functions = new Set();
  const variables = new Set();

  const fnRegex = /^\s*fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/gm;
  let match = fnRegex.exec(source);
  while (match) {
    functions.add(match[1]);
    const params = match[2]
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    for (const param of params) {
      if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(param)) {
        variables.add(param);
      }
    }
    match = fnRegex.exec(source);
  }

  const letRegex = /^\s*let\s+([A-Za-z_][A-Za-z0-9_]*)\b/gm;
  match = letRegex.exec(source);
  while (match) {
    variables.add(match[1]);
    match = letRegex.exec(source);
  }

  return { functions: [...functions], variables: [...variables] };
}

function buildDiagnostics(document) {
  const diagnostics = [];
  const text = document.getText();
  const lines = text.split(/\r?\n/);

  const braceStack = [];
  const parenStack = [];

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    const trimmed = line.trim();

    if (trimmed.startsWith("let ") && !trimmed.includes("=")) {
      const start = line.indexOf("let");
      diagnostics.push(
        new vscode.Diagnostic(
          new vscode.Range(lineIndex, Math.max(start, 0), lineIndex, Math.max(start, 0) + 3),
          "let declaration should include '=' (example: let name = value)",
          vscode.DiagnosticSeverity.Error
        )
      );
    }

    if (trimmed.startsWith("fn ") && !trimmed.includes("(") ) {
      const start = line.indexOf("fn");
      diagnostics.push(
        new vscode.Diagnostic(
          new vscode.Range(lineIndex, Math.max(start, 0), lineIndex, Math.max(start, 0) + 2),
          "Function declaration is missing '(' after function name.",
          vscode.DiagnosticSeverity.Error
        )
      );
    }

    const returnStart = line.search(/\breturn\b/);
    if (returnStart >= 0 && !isInsideFunction(lineIndex, lines)) {
      diagnostics.push(
        new vscode.Diagnostic(
          new vscode.Range(lineIndex, returnStart, lineIndex, returnStart + 6),
          "return used outside of a function block.",
          vscode.DiagnosticSeverity.Warning
        )
      );
    }

    let inString = false;
    let escaped = false;

    for (let col = 0; col < line.length; col += 1) {
      const char = line[col];
      const next = col + 1 < line.length ? line[col + 1] : "";

      if (!inString && char === "/" && next === "/") {
        break;
      }

      if (char === '"' && !escaped) {
        inString = !inString;
      }

      if (!inString) {
        if (char === "{") {
          braceStack.push({ line: lineIndex, col });
        } else if (char === "}") {
          if (!braceStack.length) {
            diagnostics.push(
              new vscode.Diagnostic(
                new vscode.Range(lineIndex, col, lineIndex, col + 1),
                "Unmatched closing brace '}'.",
                vscode.DiagnosticSeverity.Error
              )
            );
          } else {
            braceStack.pop();
          }
        } else if (char === "(") {
          parenStack.push({ line: lineIndex, col });
        } else if (char === ")") {
          if (!parenStack.length) {
            diagnostics.push(
              new vscode.Diagnostic(
                new vscode.Range(lineIndex, col, lineIndex, col + 1),
                "Unmatched closing parenthesis ')'.",
                vscode.DiagnosticSeverity.Error
              )
            );
          } else {
            parenStack.pop();
          }
        }
      }

      escaped = char === "\\" && !escaped;
      if (char !== "\\") {
        escaped = false;
      }
    }

    if (inString) {
      diagnostics.push(
        new vscode.Diagnostic(
          new vscode.Range(lineIndex, Math.max(line.length - 1, 0), lineIndex, line.length),
          "Unterminated string literal.",
          vscode.DiagnosticSeverity.Error
        )
      );
    }
  }

  for (const open of braceStack) {
    diagnostics.push(
      new vscode.Diagnostic(
        new vscode.Range(open.line, open.col, open.line, open.col + 1),
        "Unclosed opening brace '{'.",
        vscode.DiagnosticSeverity.Error
      )
    );
  }

  for (const open of parenStack) {
    diagnostics.push(
      new vscode.Diagnostic(
        new vscode.Range(open.line, open.col, open.line, open.col + 1),
        "Unclosed opening parenthesis '('.",
        vscode.DiagnosticSeverity.Error
      )
    );
  }

  return diagnostics;
}

function isInsideFunction(targetLineIndex, lines) {
  let depth = 0;

  for (let i = 0; i <= targetLineIndex; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();

    if (/^fn\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*\{\s*$/.test(trimmed)) {
      depth += 1;
      continue;
    }

    for (const char of line) {
      if (char === "{") {
        depth += 1;
      } else if (char === "}") {
        depth = Math.max(depth - 1, 0);
      }
    }
  }

  return depth > 0;
}

module.exports = {
  activate,
  deactivate,
};

