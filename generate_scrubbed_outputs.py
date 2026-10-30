
from pathlib import Path

from app.domain.pii.detectors import find_sensitive_matches
from app.services.document_processing_service import (
    DocumentProcessingService,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = (BASE_DIR / "data").resolve()
OUTPUT_DIR = (
    BASE_DIR / "submission" / "scrubbed_outputs"
).resolve()

EXPECTED_FILES = [
    "crescent_bank_statement_apr2026.pdf",
    "international_bank_statements_apr2026.docx",
    "paypal_activity_apr2026.txt",
    "wallet_transactions.csv",
]

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv"}

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def stop(message: str) -> None:
    raise SystemExit(f"STOP: {message} No outputs were written.")


def main() -> None:
    if not DATA_DIR.is_dir():
        stop("The data directory is unavailable.")

    if not OUTPUT_DIR.is_relative_to(BASE_DIR):
        stop("Output directory is outside the project.")

    if OUTPUT_DIR.exists():
        if not OUTPUT_DIR.is_dir():
            stop("Output path exists but is not a directory.")

        if any(OUTPUT_DIR.iterdir()):
            stop(
                "Output directory is not empty. "
                "Existing files will not be overwritten."
            )

    # Reject unexpected files, including files in subdirectories.
    all_files = [
        path for path in DATA_DIR.rglob("*")
        if path.is_file() or path.is_symlink()
    ]

    if len(all_files) != len(EXPECTED_FILES):
        stop("The data directory does not contain exactly four files.")

    supplied_paths = []

    for filename in EXPECTED_FILES:
        path = DATA_DIR / filename

        if not path.exists() or path.is_symlink():
            stop(f"An expected regular file is missing or unsafe: {filename}")

        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(DATA_DIR)
        except (OSError, ValueError):
            stop(f"File path validation failed: {filename}")

        if not resolved.is_file():
            stop(f"Expected file is not a regular file: {filename}")

        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
            stop(f"Unsupported file extension: {filename}")

        if resolved.stat().st_size > MAX_FILE_SIZE_BYTES:
            stop(f"File exceeds the size limit: {filename}")

        supplied_paths.append(resolved)

    service = DocumentProcessingService(DATA_DIR)

    # Process exactly the four validated paths.
    # No database persistence method is called here.
    result = service.process_directory(
        supplied_paths,
        max_file_size_bytes=MAX_FILE_SIZE_BYTES,
    )

    if (
        not isinstance(result, dict)
        or result.get("status") != "success"
        or result.get("safe_to_send") is not True
        or result.get("failed_count") != 0
        or result.get("success_count") != len(EXPECTED_FILES)
    ):
        stop("The complete batch did not pass processing validation.")

    processed = result.get("processed_files")

    if not isinstance(processed, list):
        stop("Invalid processed-file result.")

    if len(processed) != len(EXPECTED_FILES):
        stop("The processed-file count is incorrect.")

    expected_names = set(EXPECTED_FILES)
    received_names = set()
    validated_outputs = []

    for item in processed:
        if not isinstance(item, dict):
            stop("Malformed processed-file result.")

        filename = item.get("file_name")
        output = item.get("scrubbed_output")

        if filename not in expected_names:
            stop("Unexpected output filename.")

        if filename in received_names:
            stop("Duplicate output filename.")

        received_names.add(filename)

        if (
            item.get("status") != "success"
            or item.get("safe_to_send") is not True
            or not isinstance(output, str)
            or not output.strip()
            or item.get("warnings") != []
        ):
            stop("A document did not pass individual validation.")

        # Independently scan each output.
        is_csv = Path(filename).suffix.lower() == ".csv"

        if find_sensitive_matches(output, is_csv=is_csv):
            stop("Sensitive information was detected in an output.")

        validated_outputs.append((filename, output.strip()))

    if received_names != expected_names:
        stop("The expected output files do not match the processed files.")

    # Build ONE combined output with a header for every file.
    combined_output = "\n\n".join(
        f"---- File: {filename} ----\n{output}"
        for filename, output in validated_outputs
    )

    # Validate the complete combined output as ordinary text.
    if find_sensitive_matches(combined_output, is_csv=False):
        stop("Sensitive information was detected in combined output.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    destination = OUTPUT_DIR / "combined_scrubbed_output.txt"

    if destination.exists():
        stop("The combined output already exists.")

        created = False

    try:
        # Exclusive creation prevents overwriting an existing file.
        with destination.open("x", encoding="utf-8") as file:
            created = True
            file.write(combined_output + "\n")

    except Exception:
        # Only remove a file if this script successfully created it.
        if created:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass

        stop("Writing the combined output failed.")

    print("Batch status: success")
    print("Files processed:", len(validated_outputs))
    print("Failed files: 0")
    print("One combined output saved successfully.")


if __name__ == "__main__":
    main()
