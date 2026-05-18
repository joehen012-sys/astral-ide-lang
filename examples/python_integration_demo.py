from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from astral import AstralEngine, run_astral_file, run_astral_source
except ModuleNotFoundError:
    # Fallback for executions where the project root is not on sys.path.
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from astral import AstralEngine, run_astral_file, run_astral_source


def main() -> None:
    print("=== 1) One-shot source execution ===")
    run_astral_source('print "Hello from Python integration"')

    print("\n=== 2) Run an existing .ast file ===")
    showcase_path = Path(__file__).resolve().parent / "showcase.ast"
    run_astral_file(str(showcase_path))

    print("\n=== 3) Persistent engine state ===")
    engine = AstralEngine()
    engine.run_source("let x = 7")
    engine.run_source("fn double(n) { return n * 2 }")
    engine.run_source('print "x:"')
    engine.run_source("print x")
    engine.run_source('print "double(x):"')
    engine.run_source("print double(x)")


if __name__ == "__main__":
    main()




