from __future__ import annotations

from pathlib import Path


class ExtractionError(RuntimeError):
    """Raised when a document cannot be extracted safely."""


def extract_text_from_txt(file_path: str | Path) -> str:
    path = Path(file_path)
    if path.suffix.lower() != ".txt":
        raise ExtractionError("File is not a TXT document.")

    try:
        return path.read_text(encoding="utf-8-sig").strip()
    except Exception as exc:  # pragma: no cover - defensive path
        raise ExtractionError(f"Failed to extract text from TXT: {exc}") from exc
