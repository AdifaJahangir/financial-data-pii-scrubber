
from __future__ import annotations

import re


SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [

    # Explicitly labelled personal names.
    # "Customer: Jane Doe" is intentionally preserved.
    (
        "person_name",
        re.compile(
            r"(?im)^[ \t]*(?:"
            r"name|account[ \t]+holder|account[ \t]+owner|"
            r"customer[ \t]+name|cardholder"
            r")[ \t]*[:#-][ \t]*"
            r"([A-Z][A-Za-z'’-]*(?:[ \t]+[A-Z][A-Za-z'’-]*){1,3})"
            r"[ \t]*$"
        ),
        "[REDACTED_NAME]",
    ),

    # Email addresses.
    (
        "email",
        re.compile(
            r"(?<![\w.+-])"
            r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
            r"(?![\w.-])"
        ),
        "[REDACTED_EMAIL]",
    ),

    # IBAN, including spaces and lowercase variants.
    (
        "iban",
        re.compile(
            r"(?i)\biban\b[ \t]*[:#-]?[ \t]*"
            r"([A-Z]{2}[0-9A-Z ]{13,32})"
        ),
        "[REDACTED_IBAN]",
    ),

    # SWIFT / BIC.
    (
        "swift",
        re.compile(
            r"(?i)\b(?:swift|bic)\b[ \t]*[:#-]?[ \t]*"
            r"([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b"
        ),
        "[REDACTED_SWIFT]",
    ),

    # IFSC.
    (
        "ifsc",
        re.compile(
            r"(?i)\bifsc\b[ \t]*[:#-]?[ \t]*"
            r"([A-Z]{4}0[A-Z0-9]{6})\b"
        ),
        "[REDACTED_IFSC]",
    ),

    # Bank account numbers and common label variants.
    (
        "account",
        re.compile(
            r"(?i)\b(?:"
            r"account(?:[ \t]+(?:number|no\.?))?"
            r"|acct(?:[ \t]*no\.?)?"
            r"|a[ \t]*/[ \t]*c(?:[ \t]+no\.?)?"
            r"|acc"
            r")\b[ \t]*[:#=-]?[ \t]*"
            r"((?=[A-Z0-9-]*\d)[A-Z0-9-]{6,30})\b"
        ),
        "[REDACTED_ACCOUNT]",
    ),

    # Routing, ABA and transit identifiers.
    (
        "routing",
        re.compile(
            r"(?i)\b(?:routing(?:[ \t]+number)?|aba|transit)"
            r"\b[ \t]*[:#-]?[ \t]*"
            r"(\d{8,9})\b"
        ),
        "[REDACTED_ROUTING]",
    ),

    # Sort code and BSB formats.
    (
        "sort_code",
        re.compile(
            r"(?i)\b(?:sort[ \t]*code|bsb)\b"
            r"[ \t]*[:#-]?[ \t]*"
            r"(\d{2}[- ]\d{2}[- ]\d{2}|\d{3}[- ]\d{3})\b"
        ),
        "[REDACTED_SORT_CODE]",
    ),

    # Labelled phone numbers.
    (
        "phone",
        re.compile(
            r"(?i)\b(?:phone|mobile|telephone|tel|cell)"
            r"\b[ \t]*[:#-]?[ \t]*"
            r"(\+?\d[\d ().-]{7,20}\d)\b"
        ),
        "[REDACTED_PHONE]",
    ),

    # Credit and debit card numbers.
    (
        "card",
        re.compile(
            r"(?i)\b(?:"
            r"card(?:[ \t]+(?:number|no\.?))?"
            r"|credit[ \t]+card"
            r"|debit[ \t]+card"
            r"|payment[ \t]*card"
            r")\b[ \t]*[:#-][ \t]*"
            r"((?:\d[ -]?){12,18}\d)\b"
        ),
        "[REDACTED_CARD]",
    ),

    # Pakistani CNIC: formatted or 13-digit unformatted.
    (
        "cnic",
        re.compile(
            r"(?i)\bcnic\b[ \t]*(?:number|no\.?)?[ \t]*[:#-][ \t]*"
            r"(\d{5}-\d{7}-\d|\d{13})\b"
        ),
        "[REDACTED_CNIC]",
    ),

    # Labelled consumer numbers.
    (
        "consumer_number",
        re.compile(
            r"(?i)\bconsumer[ \t]+(?:number|no\.?|id)"
            r"\b[ \t]*[:#-][ \t]*"
            r"([A-Z0-9][A-Z0-9 -]{4,30}[A-Z0-9])\b"
        ),
        "[REDACTED_CONSUMER_NUMBER]",
    ),

    # Labelled wallet identifiers.
    (
        "wallet_id",
        re.compile(
            r"(?i)\bwallet[ \t]+(?:id|number|no\.?)"
            r"\b[ \t]*[:#-][ \t]*"
            r"([A-Z0-9][A-Z0-9_-]{4,38}[A-Z0-9])\b"
        ),
        "[REDACTED_WALLET_ID]",
    ),

    # Explicitly labelled national identifiers.
    (
        "national_id",
        re.compile(
            r"(?i)\b(?:"
            r"national(?:[ \t]+id)?"
            r"|ssn|dni|tax[ \t]+id|passport"
            r"|aadhaar|aadhar|pan|sin"
            r"|ni[ \t]+number|social[ \t]+insurance"
            r")\b[ \t]*[:#-]?[ \t]*"
            r"([A-Z0-9-]{6,20})\b"
        ),
        "[REDACTED_NATIONAL_ID]",
    ),

    # Payment handles.
    (
        "payment_handle",
        re.compile(
            r"(?<![A-Za-z0-9._+-])"
            r"([A-Za-z0-9._+-]{2,50}@[A-Za-z0-9._-]{2,50})"
            r"(?![A-Za-z0-9._-])"
        ),
        "[REDACTED_HANDLE]",
    ),

    # Transaction references and trace identifiers.
    (
        "long_reference",
        re.compile(
            r"(?i)\b(?:"
            r"reference|ref|transaction[ \t]+reference"
            r"|transaction[ \t]+id|trace|utr"
            r")\b[ \t]*[:#-]?[ \t]*"
            r"([A-Z0-9-]{12,32})\b"
        ),
        "[REDACTED_REFERENCE]",
    ),

    # Labelled residential and mailing addresses.
    (
        "address",
        re.compile(
            r"(?im)^[ \t]*(?:"
            r"home[ \t]+address|billing[ \t]+address|"
            r"residential[ \t]+address|mailing[ \t]+address|"
            r"street[ \t]+address|address"
            r")[ \t]*[:=][ \t]*"
            r"(\d{1,6}[ \t]+.*\b(?:"
            r"street|st|road|rd|avenue|ave|boulevard|blvd|"
            r"lane|ln|drive|dr|court|ct|way|place|pl|"
            r"circle|cir|highway|hwy"
            r")\b.*)$"
        ),
        "[REDACTED_ADDRESS]",
    ),
]
