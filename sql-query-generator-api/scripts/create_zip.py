"""Package project source into a zip (excludes venv and caches)."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT.parent / "sql-query-generator-api.zip"

SKIP_DIRS = {"venv", ".venv", "__pycache__", ".pytest_cache", ".git"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    return path.suffix in SKIP_SUFFIXES


def main() -> None:
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in ROOT.rglob("*"):
            if not file_path.is_file() or should_skip(file_path):
                continue
            arcname = file_path.relative_to(ROOT.parent)
            zf.write(file_path, arcname)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
