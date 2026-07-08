from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATH_PARTS = {
    ".ai-link",
    "raw",
    "runtime",
    "wiki",
}
FORBIDDEN_PREFIXES = {
    ("public", "data"),
}
SKIP_DIRS = {
    ".git",
    ".github",
    ".venv",
    "__pycache__",
    "node_modules",
}
SKIP_CONTENT_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
}
SECRET_PATTERNS = {
    "github token": re.compile(r"gh[opsu]_[A-Za-z0-9_]{20,}"),
    "openai style key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}", re.I),
}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def path_errors(path: Path) -> list[str]:
    rel_parts = path.relative_to(ROOT).parts
    errors = []
    if any(part in FORBIDDEN_PATH_PARTS for part in rel_parts):
        errors.append(f"forbidden private path: {path.relative_to(ROOT).as_posix()}")
    for prefix in FORBIDDEN_PREFIXES:
        if rel_parts[: len(prefix)] == prefix:
            errors.append(f"forbidden generated data path: {path.relative_to(ROOT).as_posix()}")
    if path.name.startswith(".env"):
        errors.append(f"forbidden environment file: {path.relative_to(ROOT).as_posix()}")
    return errors


def content_errors(path: Path) -> list[str]:
    if path.suffix.lower() in SKIP_CONTENT_SUFFIXES:
        return []
    if path.name.endswith(".min.js"):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    errors = []
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            errors.append(f"{name} pattern in {path.relative_to(ROOT).as_posix()}")
    return errors


def main() -> int:
    errors = []
    for path in iter_files():
        errors.extend(path_errors(path))
        errors.extend(content_errors(path))
    if errors:
        print("Public scope check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public scope OK: no private wiki source, generated data, runtime files, or obvious secrets found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
