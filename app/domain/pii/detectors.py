
from __future__ import annotations

import csv
import io
import re


# Detect likely sensitive values in ordinary text.
# Never return the actual matched value.
FINAL_SAFETY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "email",
        re.compile(
            r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
        ),
    ),
    (
        "iban",
        re.compile(
            r"(?i)\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b"
        ),
    ),
    (
        "phone",
        re.compile(
            r"(?<!\w)\+\d{1,3}(?:[\s().-]*\d){7,14}(?!\w)"
        ),
    ),
    (
        "pakistani_phone",
        re.compile(
            r"(?<!\d)(?:03\d{2}[\s-]?\d{7}|92\d{10})(?!\d)"
        ),
    ),
    (
        "cnic",
        re.compile(
            r"(?<!\d)\d{5}-\d{7}-\d(?!\d)|(?<!\d)\d{13}(?!\d)"
        ),
    ),
    (
        "labelled_identifier",
        re.compile(
            r"(?im)\b(?:"
            r"account(?:\s+number|\s+no\.?)?|acct\.?|a/c|acc\.?|"
            r"card(?:\s+number|\s+no\.?)?|"
            r"routing(?:\s+number|\s+no\.?)?|"
            r"transit(?:\s+number|\s+no\.?)?|"
            r"sort\s+code|bsb|"
            r"consumer\s+(?:number|no\.?|id)|"
            r"wallet\s+(?:id|number|no\.?)|"
            r"transaction\s+(?:id|reference)|"
            r"reference(?:\s+number|\s+no\.?)?|"
            r"trace(?:\s+number|\s+no\.?)?|utr|"
            r"national\s+id|passport|"
            r"ssn|aadhaar|pan|sin|"
            r"ifsc|swift|bic"
            r")\s*[:#=-]\s*[A-Z0-9][A-Z0-9 /-]{3,35}"
        ),
    ),
    (
        "labelled_address",
        re.compile(
            r"(?im)\b(?:residential|mailing|billing|home|street)"
            r"\s+address\s*[:=]\s*.+"
        ),
    ),
    (
        "labelled_postal_code",
        re.compile(
            r"(?im)\b(?:postal\s+code|postcode|zip\s+code|zip)"
            r"\s*[:=]\s*[A-Z0-9][A-Z0-9 -]{2,12}"
        ),
    ),
]


# Exact normalized CSV headers containing sensitive information.
# Safe financial fields such as Amount, Balance, Date and Order Number
# are intentionally excluded.
SENSITIVE_CSV_HEADERS: dict[str, str] = {
    "account": "account",
    "account number": "account",
    "account no": "account",
    "account no.": "account",
    "acct": "account",
    "acct no": "account",
    "a/c": "account",
    "a/c no": "account",
    "card": "card",
    "card number": "card",
    "card no": "card",
    "credit card": "card",
    "debit card": "card",
    "routing": "routing",
    "routing number": "routing",
    "routing no": "routing",
    "aba": "routing",
    "transit number": "routing",
    "sort code": "sort_code",
    "bsb": "sort_code",
    "iban": "iban",
    "swift": "swift",
    "swift code": "swift",
    "bic": "swift",
    "ifsc": "ifsc",
    "cnic": "cnic",
    "national id": "national_id",
    "national id number": "national_id",
    "passport": "national_id",
    "passport number": "national_id",
    "ssn": "national_id",
    "tax id": "national_id",
    "aadhaar": "national_id",
    "pan": "national_id",
    "sin": "national_id",
    "ni number": "national_id",
    "consumer number": "consumer_number",
    "consumer no": "consumer_number",
    "consumer id": "consumer_number",
    "wallet id": "wallet_id",
    "wallet number": "wallet_id",
    "wallet no": "wallet_id",
    "payment id": "wallet_id",
    "payment handle": "payment_handle",
    "transaction id": "long_reference",
    "transaction reference": "long_reference",
    "reference": "long_reference",
    "reference number": "long_reference",
    "reference no": "long_reference",
    "trace": "long_reference",
    "trace number": "long_reference",
    "utr": "long_reference",
    "phone": "phone",
    "phone number": "phone",
    "mobile": "phone",
    "mobile number": "phone",
    "telephone": "phone",
    "email": "email",
    "email address": "email",
    "e-mail": "email",
    "address": "address",
    "residential address": "address",
    "mailing address": "address",
    "billing address": "address",
    "customer address": "address",
}


# Sensitive metadata labels that may appear before a CSV transaction table.
# A generic "Customer" label is deliberately not treated as a person's name.
SENSITIVE_METADATA_LABELS: dict[str, str] = {
    "customer name": "person_name",
    "account holder": "person_name",
    "account owner": "person_name",
    "cardholder": "person_name",
    "account number": "account",
    "account no": "account",
    "wallet account number": "account",
    "wallet id": "wallet_id",
    "wallet number": "wallet_id",
    "iban": "iban",
    "registered cnic": "cnic",
    "cnic": "cnic",
    "national id": "national_id",
    "registered email": "email",
    "email address": "email",
    "email": "email",
    "linked card": "card",
    "card number": "card",
    "phone number": "phone",
    "mobile number": "phone",
    "address": "address",
    "residential address": "address",
    "mailing address": "address",
}


def _normalize_header(value: str) -> str:
    """Normalize CSV headers and metadata labels."""
    value = value.strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.rstrip(":").strip()


def _is_plausible_transaction_header(row: list[str]) -> bool:
    """Identify a likely transaction-table header."""
    normalized = {_normalize_header(cell) for cell in row}

    transaction_columns = {
        "timestamp",
        "date",
        "transaction date",
        "type",
        "description",
        "amount",
        "balance",
        "merchant",
    }

    return len(normalized.intersection(transaction_columns)) >= 2


def _find_csv_header_index(rows: list[list[str]]) -> int | None:
    """Find a transaction header, including when metadata precedes it."""
    for index, row in enumerate(rows):
        if _is_plausible_transaction_header(row):
            return index

    # Support simple CSV files whose first row contains sensitive headers.
    for index, row in enumerate(rows):
        normalized = {_normalize_header(cell) for cell in row}

        if normalized.intersection(SENSITIVE_CSV_HEADERS):
            return index

    return None


def _find_csv_sensitive_headers(
    document_text: str,
) -> list[tuple[str, str]]:
    """
    Inspect CSV metadata and sensitive transaction columns.

    Returned values are generic markers, never actual document contents.
    """
    try:
        reader = csv.reader(
            io.StringIO(document_text, newline=""),
            strict=True,
        )
        rows = list(reader)

        if not rows:
            return []

        matches: list[tuple[str, str]] = []

        header_index = _find_csv_header_index(rows)

        # Check key/value metadata before the transaction table.
        metadata_rows = (
            rows[:header_index]
            if header_index is not None
            else rows
        )

        for row in metadata_rows:
            if len(row) < 2:
                continue

            label = _normalize_header(row[0])

            if label in SENSITIVE_METADATA_LABELS:
                if any(cell.strip() for cell in row[1:]):
                    matches.append(
                        ("labelled_identifier", "[POTENTIAL_IDENTIFIER]")
                    )

        if header_index is None:
            return matches

        headers = [
            _normalize_header(cell)
            for cell in rows[header_index]
        ]

        sensitive_indexes = [
            index
            for index, header in enumerate(headers)
            if header in SENSITIVE_CSV_HEADERS
        ]

        for row in rows[header_index + 1:]:
            for index in sensitive_indexes:
                if index < len(row) and row[index].strip():
                    matches.append(
                        ("labelled_identifier", "[POTENTIAL_IDENTIFIER]")
                    )

        return matches

    except (csv.Error, UnicodeError, ValueError):
        # Malformed CSV must never be considered safe.
        return [
            ("csv_parse_error", "[POTENTIAL_IDENTIFIER]")
        ]


def find_sensitive_matches(
    document_text: str,
    *,
    is_csv: bool | None = None,
) -> list[tuple[str, str]]:
    """
    Independently detect possible sensitive information.

    is_csv=True:
        Strict CSV inspection.

    is_csv=False:
        Ordinary text inspection only.

    is_csv=None:
        Legacy automatic CSV detection for existing callers and tests.

    Each result is a (category, safe_marker) tuple.
    Actual matched sensitive values are never returned.
    """
    if not isinstance(document_text, str) or not document_text.strip():
        return []

    matches: list[tuple[str, str]] = []

    # Remove redaction placeholders before running detection.
    text_to_check = re.sub(
        r"\[REDACTED_[A-Z_]+\]",
        "",
        document_text,
        flags=re.IGNORECASE,
    )

    if is_csv is True:
        matches.extend(
            _find_csv_sensitive_headers(text_to_check)
        )

    elif is_csv is None:
        # Preserve compatibility with existing callers that do not
        # explicitly specify whether their input is CSV.
        try:
            rows = list(
                csv.reader(
                    io.StringIO(text_to_check, newline=""),
                    strict=True,
                )
            )

            if rows and _find_csv_header_index(rows) is not None:
                matches.extend(
                    _find_csv_sensitive_headers(text_to_check)
                )

        except (csv.Error, UnicodeError, ValueError):
            # Do not interpret ordinary text as malformed CSV.
            pass

    for category, pattern in FINAL_SAFETY_PATTERNS:
        if pattern.search(text_to_check):
            matches.append(
                (category, "[POTENTIAL_IDENTIFIER]")
            )

    return matches
