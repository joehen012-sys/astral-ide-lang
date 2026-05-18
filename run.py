from __future__ import annotations

import sys

from astral.cli import repl, run_file


def main() -> int:
    if len(sys.argv) > 2:
        print("Usage: python run.py [script.ast]")
        return 64

    if len(sys.argv) == 2:
        return run_file(sys.argv[1])

    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
