
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from app.domain.pii.detectors import find_sensitive_matches
from app.domain.pii.rules import SENSITIVE_PATTERNS
from app.domain.pii.validation import is_valid_candidate


@dataclass
class ScrubResult:
    text: str
    redacted_count: int = 0
    warnings: list[str] = field(default_factory=list)
    safe_to_send: bool = True


class ScrubbingFailureError(RuntimeError):
    """Raised when document sanitization cannot safely proceed."""


CSV_SENSITIVE_HEADERS: dict[str, str] = {
    "account": "[REDACTED_ACCOUNT]",
    "account number": "[REDACTED_ACCOUNT]",
    "account no": "[REDACTED_ACCOUNT]",
    "account no.": "[REDACTED_ACCOUNT]",
    "acct": "[REDACTED_ACCOUNT]",
    "acct no": "[REDACTED_ACCOUNT]",
    "a/c": "[REDACTED_ACCOUNT]",
    "a/c no": "[REDACTED_ACCOUNT]",
    "card": "[REDACTED_CARD]",
    "card number": "[REDACTED_CARD]",
    "card no": "[REDACTED_CARD]",
    "credit card": "[REDACTED_CARD]",
    "debit card": "[REDACTED_CARD]",
    "routing": "[REDACTED_ROUTING]",
    "routing number": "[REDACTED_ROUTING]",
    "routing no": "[REDACTED_ROUTING]",
    "aba": "[REDACTED_ROUTING]",
    "transit number": "[REDACTED_ROUTING]",
    "sort code": "[REDACTED_SORT_CODE]",
    "bsb": "[REDACTED_SORT_CODE]",
    "iban": "[REDACTED_IBAN]",
    "swift": "[REDACTED_SWIFT]",
    "swift code": "[REDACTED_SWIFT]",
    "bic": "[REDACTED_SWIFT]",
    "ifsc": "[REDACTED_IFSC]",
    "cnic": "[REDACTED_CNIC]",
    "national id": "[REDACTED_NATIONAL_ID]",
    "national id number": "[REDACTED_NATIONAL_ID]",
    "passport": "[REDACTED_NATIONAL_ID]",
    "passport number": "[REDACTED_NATIONAL_ID]",
    "ssn": "[REDACTED_NATIONAL_ID]",
    "tax id": "[REDACTED_NATIONAL_ID]",
    "aadhaar": "[REDACTED_NATIONAL_ID]",
    "pan": "[REDACTED_NATIONAL_ID]",
    "sin": "[REDACTED_NATIONAL_ID]",
    "ni number": "[REDACTED_NATIONAL_ID]",
    "consumer number": "[REDACTED_CONSUMER_NUMBER]",
    "consumer no": "[REDACTED_CONSUMER_NUMBER]",
    "consumer id": "[REDACTED_CONSUMER_NUMBER]",
    "wallet id": "[REDACTED_WALLET_ID]",
    "wallet number": "[REDACTED_WALLET_ID]",
    "wallet no": "[REDACTED_WALLET_ID]",
    "payment id": "[REDACTED_WALLET_ID]",
    "payment handle": "[REDACTED_HANDLE]",
    "transaction id": "[REDACTED_REFERENCE]",
    "transaction reference": "[REDACTED_REFERENCE]",
    "reference": "[REDACTED_REFERENCE]",
    "reference number": "[REDACTED_REFERENCE]",
    "reference no": "[REDACTED_REFERENCE]",
    "trace": "[REDACTED_REFERENCE]",
    "trace number": "[REDACTED_REFERENCE]",
    "utr": "[REDACTED_REFERENCE]",
    "phone": "[REDACTED_PHONE]",
    "phone number": "[REDACTED_PHONE]",
    "mobile": "[REDACTED_PHONE]",
    "mobile number": "[REDACTED_PHONE]",
    "telephone": "[REDACTED_PHONE]",
    "email": "[REDACTED_EMAIL]",
    "email address": "[REDACTED_EMAIL]",
    "e-mail": "[REDACTED_EMAIL]",
    "address": "[REDACTED_ADDRESS]",
    "residential address": "[REDACTED_ADDRESS]",
    "mailing address": "[REDACTED_ADDRESS]",
    "billing address": "[REDACTED_ADDRESS]",
    "customer address": "[REDACTED_ADDRESS]",
}

CSV_METADATA_LABELS: dict[str, str] = {
    "customer name": "[REDACTED_NAME]",
    "account holder": "[REDACTED_NAME]",
    "account owner": "[REDACTED_NAME]",
    "cardholder": "[REDACTED_NAME]",
    "account number": "[REDACTED_ACCOUNT]",
    "account no": "[REDACTED_ACCOUNT]",
    "wallet account number": "[REDACTED_ACCOUNT]",
    "wallet id": "[REDACTED_WALLET_ID]",
    "wallet number": "[REDACTED_WALLET_ID]",
    "iban": "[REDACTED_IBAN]",
    "registered cnic": "[REDACTED_CNIC]",
    "cnic": "[REDACTED_CNIC]",
    "national id": "[REDACTED_NATIONAL_ID]",
    "registered email": "[REDACTED_EMAIL]",
    "email address": "[REDACTED_EMAIL]",
    "email": "[REDACTED_EMAIL]",
    "linked card": "[REDACTED_CARD]",
    "card number": "[REDACTED_CARD]",
    "phone number": "[REDACTED_PHONE]",
    "mobile number": "[REDACTED_PHONE]",
    "address": "[REDACTED_ADDRESS]",
    "residential address": "[REDACTED_ADDRESS]",
    "mailing address": "[REDACTED_ADDRESS]",
}

TRANSACTION_HEADERS = {
    "timestamp",
    "date",
    "transaction date",
    "type",
    "description",
    "amount",
    "balance",
    "merchant",
}


def _normalize_header(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.rstrip(":").strip()


def _find_csv_header_index(rows: list[list[str]]) -> int | None:
    """Locate the transaction table, allowing preceding metadata rows."""
    for index, row in enumerate(rows):
        normalized = {_normalize_header(cell) for cell in row}

        if len(normalized.intersection(TRANSACTION_HEADERS)) >= 2:
            return index

    # Support simple CSV files with sensitive headers and few other columns.
    for index, row in enumerate(rows):
        normalized = {_normalize_header(cell) for cell in row}

        if normalized.intersection(CSV_SENSITIVE_HEADERS):
            return index

    return None


def _failure(message: str) -> ScrubResult:
    """Create a failure result without exposing source content."""
    return ScrubResult(
        text="",
        redacted_count=0,
        warnings=[message],
        safe_to_send=False,
    )


def _scrub_plain_text(document_text: str) -> ScrubResult:
    """Apply the existing text-based PII rules."""
    try:
        sanitized = document_text
                # Fail closed for recognizable Pakistani house/street address formats.
        pakistani_address_pattern = re.compile(
            r"(?im)^[ \t]*address[ \t]*:[ \t]*"
            r"(?=.*\bhouse\b)"
            r"(?=.*\bstreet\b)"
            r".+$"
        )

        if pakistani_address_pattern.search(sanitized):
            return _failure(
                "A potentially sensitive residential address was detected; "
                "document was not marked safe to send."
            )
        redacted_count = 0

        # Explicitly labelled UPI IDs.
        upi_pattern = re.compile(
            r"(?im)^[ \t]*UPI[ \t]+ID[ \t]*:[ \t]*([^\s,;]+)"
        )

        upi_matches = list(upi_pattern.finditer(sanitized))
        redacted_count += len(upi_matches)

        sanitized = upi_pattern.sub(
            "UPI ID: [REDACTED_HANDLE]",
            sanitized,
        )

        # Reject malformed values explicitly labelled as email addresses.
        labelled_email_pattern = re.compile(
            r"(?im)\b(?:email|e-mail)\s*[:=]\s*([^\s,;]+)"
        )

        valid_email_pattern = re.compile(
            r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        )

        for match in labelled_email_pattern.finditer(sanitized):
            candidate = match.group(1).strip()

            if not valid_email_pattern.fullmatch(candidate):
                return _failure(
                    "Malformed email detected; document was not "
                    "marked safe to send."
                )
        # Fail closed when explicitly labelled identifiers are incomplete.
        incomplete_identifier_checks = [
            (
                "CNIC",
                re.compile(
                    r"(?im)\bCNIC\b[ \t]*(?:number|no\.?)?"
                    r"[ \t]*[:#-][ \t]*([^\r\n,;]*)"
                ),
                "cnic",
            ),
            (
                "consumer number",
                re.compile(
                    r"(?im)\bconsumer[ \t]+(?:number|no\.?|id)\b"
                    r"[ \t]*[:#-][ \t]*([^\r\n,;]*)"
                ),
                "consumer_number",
            ),
            (
                "wallet ID",
                re.compile(
                    r"(?im)\bwallet[ \t]+(?:id|number|no\.?)\b"
                    r"[ \t]*[:#-][ \t]*([^\r\n,;]*)"
                ),
                "wallet_id",
            ),
        ]

        for label, label_pattern, category in incomplete_identifier_checks:
            for match in label_pattern.finditer(sanitized):
                candidate = match.group(1).strip()

                if not candidate or not is_valid_candidate(
                    category,
                    candidate,
                ):
                    return _failure(
                        f"Incomplete or ambiguous {label} detected; "
                        "document was not marked safe to send."
                    )
        # Apply configured PII rules.
        for category, pattern, replacement in SENSITIVE_PATTERNS:
            ambiguous = False

            if pattern.groups != 1:
                return _failure(
                    f"Invalid {category} rule configuration; "
                    "document was not marked safe to send."
                )

            def replace_match(
                match,
                category_name=category,
                token=replacement,
            ):
                nonlocal redacted_count, ambiguous

                candidate = match.group(1).strip()

                if not candidate or not is_valid_candidate(
                    category_name,
                    candidate,
                ):
                    ambiguous = True
                    return match.group(0)

                redacted_count += 1
                return token

            sanitized = pattern.sub(replace_match, sanitized)

            if ambiguous:
                return _failure(
                    f"Ambiguous {category} pattern detected; "
                    "document was not marked safe to send."
                )

        # Reject any remaining email-like or payment-like identifier.
        remaining_at_pattern = re.compile(
            r"(?i)(?<![\w.+-])[\w.+-]+@[\w.-]+(?![\w.-])"
        )

        if remaining_at_pattern.search(sanitized):
            return _failure(
                "Unrecognized email-like or payment identifier "
                "remains; document was not marked safe to send."
            )

        # Recheck every configured rule after replacement.
        for category, pattern, _replacement in SENSITIVE_PATTERNS:
            if pattern.groups != 1:
                return _failure(
                    "Final safety check found an invalid "
                    "pattern configuration."
                )

            for match in pattern.finditer(sanitized):
                candidate = match.group(1).strip()

                if candidate and is_valid_candidate(
                    category,
                    candidate,
                ):
                    return _failure(
                        "Sensitive information may remain "
                        "after scrubbing."
                    )

        # Independent validation in ordinary-text mode.
        remaining_sensitive = find_sensitive_matches(
            sanitized,
            is_csv=False,
        )

        if remaining_sensitive:
            return _failure(
                "Independent safety validation detected "
                "possible sensitive information; "
                "document was not marked safe to send."
            )

        if not sanitized.strip():
            return _failure("Scrubbed output is empty.")

        return ScrubResult(
            text=sanitized,
            redacted_count=redacted_count,
            warnings=[],
            safe_to_send=True,
        )

    except Exception:
        return _failure(
            "Scrubbing failed; raw document content was not returned."
        )


def _scrub_csv(document_text: str) -> ScrubResult:
    """Redact sensitive CSV metadata, columns and description content."""
    try:
        reader = csv.reader(
            io.StringIO(document_text, newline=""),
            strict=True,
        )
        rows = list(reader)

        if not rows:
            return _failure("CSV document is empty.")

        header_index = _find_csv_header_index(rows)

        if header_index is None:
            return _failure(
                "CSV transaction headers could not be identified; "
                "document was not marked safe to send."
            )

        redacted_count = 0

        # Scrub sensitive metadata before the transaction table.
        for row in rows[:header_index]:
            if len(row) < 2:
                continue

            label = _normalize_header(row[0])
            replacement = CSV_METADATA_LABELS.get(label)

            if replacement:
                for index in range(1, len(row)):
                    if row[index].strip():
                        row[index] = replacement
                        redacted_count += 1

            else:
                # Scrub identifiers appearing in other metadata values.
                for index in range(1, len(row)):
                    result = _scrub_plain_text(row[index])

                    if not result.safe_to_send:
                        return _failure(
                            "CSV metadata could not be safely scrubbed."
                        )

                    row[index] = result.text
                    redacted_count += result.redacted_count

        headers = [
            _normalize_header(cell)
            for cell in rows[header_index]
        ]

        sensitive_columns = {
            index: CSV_SENSITIVE_HEADERS[header]
            for index, header in enumerate(headers)
            if header in CSV_SENSITIVE_HEADERS
        }

        description_columns = [
            index
            for index, header in enumerate(headers)
            if header in {"description", "transaction description"}
        ]

        expected_width = len(headers)

        if expected_width == 0:
            return _failure("CSV transaction header is empty.")

        # Validate and scrub transaction rows.
        for row in rows[header_index + 1:]:
            if len(row) != expected_width:
                return _failure(
                    "CSV row structure is inconsistent; "
                    "document was not marked safe to send."
                )

            for index, replacement in sensitive_columns.items():
                if row[index].strip():
                    row[index] = replacement
                    redacted_count += 1

            # Descriptions can contain embedded identifiers.
            for index in description_columns:
                result = _scrub_plain_text(row[index])

                if not result.safe_to_send:
                    return _failure(
                        "A transaction description could not be "
                        "safely scrubbed."
                    )

                row[index] = result.text
                redacted_count += result.redacted_count

            # Also check other cells for embedded identifiers.
            for index, value in enumerate(row):
                if index in sensitive_columns or index in description_columns:
                    continue

                result = _scrub_plain_text(value)

                if not result.safe_to_send:
                    return _failure(
                        "A CSV field could not be safely scrubbed."
                    )

                row[index] = result.text
                redacted_count += result.redacted_count

        # Rebuild CSV with proper quoting and escaping.
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(rows)

        sanitized = output.getvalue()

        # Independent CSV validation.
        remaining_sensitive = find_sensitive_matches(
            sanitized,
            is_csv=True,
        )

        if remaining_sensitive:
            return _failure(
                "Independent CSV safety validation detected "
                "possible sensitive information."
            )

        if not sanitized.strip():
            return _failure("Scrubbed CSV output is empty.")

        return ScrubResult(
            text=sanitized.rstrip("\n"),
            redacted_count=redacted_count,
            warnings=[],
            safe_to_send=True,
        )

    except (csv.Error, UnicodeError, ValueError):
        return _failure(
            "CSV parsing failed; raw document content was not returned."
        )

    except Exception:
        return _failure(
            "CSV scrubbing failed; raw document content was not returned."
        )


def scrub_document_text(
    document_text: str,
    *,
    is_csv: bool = False,
) -> ScrubResult:
    """
    Scrub ordinary text or CSV content.

    CSV processing must be explicitly enabled by the caller.
    All uncertain cases fail closed.
    """
    if not isinstance(document_text, str) or not document_text.strip():
        return _failure(
            "Document text is missing, invalid, or empty."
        )

    if is_csv:
        return _scrub_csv(document_text)

    return _scrub_plain_text(document_text)
