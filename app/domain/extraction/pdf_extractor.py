from __future__ import annotations

from pathlib import Path

import fitz


class ExtractionError(RuntimeError):
    """Raised when a document cannot be extracted safely."""


def extract_text_from_pdf(file_path: str | Path) -> str:
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        raise ExtractionError("File is not a PDF.")

    doc = None
    try:
        doc = fitz.open(path)
        pages: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if text:
                pages.append(text)
        return "\n".join(pages).strip()
    except Exception as exc:  # pragma: no cover - defensive path
        raise ExtractionError(f"Failed to extract text from PDF: {exc}") from exc
    finally:
        if doc is not None:
            doc.close()
