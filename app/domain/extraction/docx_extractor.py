from __future__ import annotations

from pathlib import Path

from docx import Document


class ExtractionError(RuntimeError):
    """Raised when a document cannot be extracted safely."""


def extract_text_from_docx(file_path: str | Path) -> str:
    path = Path(file_path)
    if path.suffix.lower() != ".docx":
        raise ExtractionError("File is not a DOCX document.")

    try:
        document = Document(str(path))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as exc:  # pragma: no cover - defensive path
        raise ExtractionError(f"Failed to extract text from DOCX: {exc}") from exc
