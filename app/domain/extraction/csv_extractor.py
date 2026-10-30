
from __future__ import annotations

import csv
import io
from pathlib import Path


class ExtractionError(RuntimeError):
    """Raised when a document cannot be extracted safely."""


def extract_text_from_csv(file_path: str | Path) -> str:
    path = Path(file_path)

    if path.suffix.lower() != ".csv":
        raise ExtractionError("File is not a CSV document.")

    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.reader(csv_file, strict=True)
            rows = list(reader)

        if not rows:
            raise ExtractionError("CSV document is empty.")

        # Re-serialize as valid CSV while preserving its row/column structure.
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(rows)

        result = output.getvalue()

        if not result.strip():
            raise ExtractionError("CSV document is empty.")

        return result

    except ExtractionError:
        raise

    except (OSError, UnicodeError, csv.Error) as exc:
        raise ExtractionError(
            "CSV extraction failed; document content was not returned."
        ) from exc
