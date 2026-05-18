# Astral Language (Python Implementation)

Astral is a small interpreted programming language built in pure Python.

## Features in v0

- Variables with `let` and reassignment
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Boolean logic: `and`, `or`, `not`
- Strings, numbers, booleans, and `nil`
- `if` blocks
- `while` loops
- `print` statements
- Functions with `fn`, parameters, and `return`
- Function calls with `name(arg1, arg2)`
- Classes with methods, instance fields (`this.name`), and constructors (`init`)
- File imports via `import "path/to/file.ast"`
- Built-ins: `len(value)` and `input(prompt)`
- Syntax errors with line/column caret pointers

## Description files

If a file is named `deci.ast`, `desc.ast`, or `description.ast`, Astral treats it as a descriptor file instead of normal Astral code.

Supported fields:

- `name`
- `version` (also accepts `verion` typo for compatibility)
- `description` (also accepts `decription` typo for compatibility)

Example descriptor:

```json
{
  "name": "example name",
  "version": "1.0.0",
  "description": "example description"
}
```

Output when run:

```text
Name: example name
Version: 1.0.0
Description: example description
```
## Syntax quick look

```text
fn greet(name) {
  return "Hello, " + name
}

print greet("Astral")

let x = 0
while x < 5 {
  print x
  x = x + 1
}

if x == 5 {
  print "five"
} elif x > 5 {
  print "big"
} else {
  print "small"
}
```

## Run a source file

```powershell
python run.py examples/examples_all.ast
```

## Easy launcher commands (Windows)

From the project folder you can use:

```powershell
./astral.ps1 examples/examples_all.ast
```

Class/import demo:

```powershell
./astral.ps1 examples/examples_all.ast
```

Or in cmd/PowerShell:

```powershell
./astral.cmd examples/examples_all.ast
```

Start REPL with no file:

```powershell
./astral.cmd
```

## Astral IDE (Python)

Run the lightweight Astral IDE with:

```powershell
./astral-ide.cmd
```

IDE features:

- Open/save `.ast` files
- Run current code
- Output panel with Astral errors
- Astral templates: **Fn Template** and **Class Template** toolbar actions
- Astral static check: **Check Astral** parses code for lexer/parser errors without running it
- Utility tools: **Insert Timestamp**, **Doc Stats**, **Format JSON**
- Settings include:
  - Editor Font Size (9–24pt)
  - Editor Font Family (monospace fonts with system fallback)
  - Theme selection (Astral Light, Astral Dark, Solar Ember, plus custom themes)
  - Editor Language (Astral or Python)
  - Autosave file before run
  - Autosave when switching files

Keyboard shortcuts:

- `Ctrl+O` open file
- `Ctrl+S` save file
- `Ctrl+R` run code
- `Ctrl+Shift+F` insert Astral function template
- `Ctrl+Shift+L` insert Astral class template
- `Ctrl+Shift+K` run Astral syntax check
- `Ctrl+Shift+T` insert timestamp
- `Ctrl+Shift+W` show document stats
- `Ctrl+Shift+J` format JSON

## Start REPL

```powershell
python run.py
```

## Use Astral from Python

```python
from astral import AstralEngine, run_astral_file, run_astral_source

# One-shot helpers
run_astral_source('print "Hello from Python host"')
run_astral_file("examples/examples_all.ast")

# Persistent engine (keeps variable/function state)
engine = AstralEngine()
engine.run_source("let x = 10")
engine.run_source("print x")
```

Inside REPL:

```text
:help
:load examples/examples_all.ast
```

## Project layout

- `astral/token.py`: token definitions
- `astral/lexer.py`: source text to tokens
- `astral/ast_nodes.py`: AST node classes
- `astral/parser.py`: tokens to AST
- `astral/interpreter.py`: AST evaluator/runtime
- `astral/cli.py`: CLI runner and REPL
- `run.py`: entry point


