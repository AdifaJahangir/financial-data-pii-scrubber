from __future__ import annotations

import csv
from pathlib import Path


class ExtractionError(RuntimeError):
    """Raised when a document cannot be extracted safely."""


def extract_text_from_csv(file_path: str | Path) -> str:
    path = Path(file_path)
    if path.suffix.lower() != ".csv":
        raise ExtractionError("File is not a CSV document.")

    rows: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                rows.append(", ".join(cell.strip() for cell in row if cell and cell.strip()))
        return "\n".join(rows).strip()
    except Exception as exc:  # pragma: no cover - defensive path
        raise ExtractionError(f"Failed to extract text from CSV: {exc}") from exc
