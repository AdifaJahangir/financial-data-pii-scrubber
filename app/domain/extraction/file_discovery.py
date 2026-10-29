from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt"}


def discover_supported_files(data_dir: str | Path) -> list[Path]:
    """Return supported files under the configured data directory only."""
    base_dir = Path(data_dir).expanduser().resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        return []

    discovered: list[Path] = []
    for candidate in sorted(base_dir.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            candidate.resolve().relative_to(base_dir)
        except ValueError:
            continue
        discovered.append(candidate.resolve())
    return discovered
