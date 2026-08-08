"""Compatibility wrapper for the Question 3 package CLI."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.Q3.__main__ import main
else:
    from .Q3.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
