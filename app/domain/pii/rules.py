
from __future__ import annotations

import re


SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
  
    (
        "person_name",
        re.compile(
            r"(?im)^\s*(?:name|account[ \t]+holder|account[ \t]+owner|"
            r"customer[ \t]+name|cardholder)[ \t]*[:#-][ \t]*"
            r"([A-Z][A-Za-z'’-]*(?:[ \t]+[A-Z][A-Za-z'’-]*){1,3})"
            r"[ \t]*$"
        ),
        "[REDACTED_NAME]",
    ),

    (
        "email",
        re.compile(
            r"(?<![\w.+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w.-])"
        ),
        "[REDACTED_EMAIL]",
    ),
    (
        "iban",
        re.compile(
            r"(?i)\biban\b\s*[:#-]?\s*([A-Z]{2}[0-9A-Z ]{13,32})"
        ),
        "[REDACTED_IBAN]",
    ),
    (
        "swift",
        re.compile(
            r"(?i)\b(?:swift|bic)\b\s*[:#-]?\s*([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b"
        ),
        "[REDACTED_SWIFT]",
    ),
    (
        "ifsc",
        re.compile(
            r"(?i)\bifsc\b\s*[:#-]?\s*([A-Z]{4}0[A-Z0-9]{6})\b"
        ),
        "[REDACTED_IFSC]",
    ),
    (
        "account",
        re.compile(
            r"(?i)\b(?:account(?:\s+number)?|acct(?:\s*no)?|checking|savings)\b\s*[:#-]?\s*([A-Z0-9-]{6,30})\b"
        ),
        "[REDACTED_ACCOUNT]",
    ),
    (
        "routing",
        re.compile(
            r"(?i)\b(?:routing|aba|transit)\b\s*[:#-]?\s*(\d{8,9})\b"
        ),
        "[REDACTED_ROUTING]",
    ),
    (
        "sort_code",
        re.compile(
            r"(?i)\b(?:sort\s*code|bsb)\b\s*[:#-]?\s*(\d{2}[- ]\d{2}[- ]\d{2})\b"
        ),
        "[REDACTED_SORT_CODE]",
    ),
    (
        "phone",
        re.compile(
            r"(?i)\b(?:phone|mobile|tel|cell)\b\s*[:#-]?\s*(\+?\d[\d ().-]{7,20}\d)\b"
        ),
        "[REDACTED_PHONE]",
    ),
    
    (
        "card",
        re.compile(
            r"(?i)\b(?:card|credit|debit|payment[ \t]*card)"
            r"\b[ \t]*[:#-][ \t]*"
            r"((?:\d[ -]?){12,18}\d)\b"
        ),
        "[REDACTED_CARD]",
    ),

    (
        "national_id",
        re.compile(
            r"(?i)\b(?:national(?:\s+id)?|ssn|dni|tax\s+id|passport)\b\s*[:#-]?\s*([A-Z0-9-]{6,20})\b"
        ),
        "[REDACTED_NATIONAL_ID]",
    ),
    (
        "payment_handle",
        re.compile(
            r"(?<!\w)(@[A-Za-z0-9._-]{2,30})\b"
        ),
        "[REDACTED_HANDLE]",
    ),
    (
        "long_reference",
        re.compile(
            r"(?i)\b(?:reference|ref|transaction\s+reference)\b\s*[:#-]?\s*([A-Z0-9-]{12,32})\b"
        ),
        "[REDACTED_REFERENCE]",
    ),
    (
        "address",
        re.compile(
            r"(?i)\b(\d+\s+[A-Za-z0-9.\- ]{1,60}?"
            r"(?:street|st|road|rd|avenue|ave|boulevard|blvd|"
            r"lane|ln|drive|dr|court|ct|way|place|pl|"
            r"circle|cir|highway|hwy))\b"
        ),
        "[REDACTED_ADDRESS]",
    ),
]
