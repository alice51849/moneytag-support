#!/usr/bin/env python3
"""Run the repository's authoritative support-site validation."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from check import main  # noqa: E402


if __name__ == "__main__":
    main()
