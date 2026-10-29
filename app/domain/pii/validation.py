
from __future__ import annotations

import re


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_iban(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def normalize_phone(value: str) -> str:
    return re.sub(r"[^0-9+]", "", value)


def is_likely_card_number(value: str) -> bool:
    digits = digits_only(value)
    return (
        13 <= len(digits) <= 19
        and digits[0] in {"3", "4", "5", "6"}
    )


def is_likely_phone_number(value: str) -> bool:
    digits = digits_only(value)
    if not 10 <= len(digits) <= 15 or digits.startswith("000"):
        return False
    return True


def is_likely_iban(value: str) -> bool:
    cleaned = normalize_iban(value)
    return (
        15 <= len(cleaned) <= 34
        and cleaned[:2].isalpha()
        and cleaned[2:4].isdigit()
        and cleaned.isalnum()
    )


def is_likely_account_number(value: str) -> bool:
    digits = digits_only(value)
    return 6 <= len(digits) <= 20


def is_likely_routing_number(value: str) -> bool:
    return len(digits_only(value)) in {8, 9}


def is_likely_sort_code(value: str) -> bool:
    return bool(
        re.fullmatch(r"\d{2}[- ]\d{2}[- ]\d{2}", value.strip())
    )


def is_likely_address(value: str) -> bool:
    lower = value.lower()
    return (
        bool(re.search(r"\d", value))
        and bool(
            re.search(
                r"\b(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|"
                r"boulevard|blvd|court|ct|way|place|pl|circle|cir|"
                r"highway|hwy)\b",
                lower,
            )
        )
    )


def is_likely_national_id(value: str) -> bool:
    digits = digits_only(value)
    return 6 <= len(digits) <= 18


def is_likely_reference(value: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value)
    return (
        12 <= len(cleaned) <= 32
        and any(ch.isdigit() for ch in cleaned)
    )


def is_valid_candidate(category: str, value: str) -> bool:
    cleaned = value.strip()

    if not cleaned:
        return False

    # Validate names captured by explicitly labelled name patterns.
    if category == "person_name":
        return bool(
            re.fullmatch(
                r"[A-Z][A-Za-z'’-]*(?:[ \t]+[A-Z][A-Za-z'’-]*){1,3}",
                cleaned,
            )
        )

    if category == "iban":
        return is_likely_iban(cleaned)

    if category == "swift":
        normalized = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
        return (
            len(normalized) in {8, 11}
            and normalized[:6].isalpha()
            and normalized[6:].isalnum()
        )

    if category == "ifsc":
        normalized = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
        return bool(
            re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", normalized)
        )

    validators = {
        "email": lambda v: bool(
            re.fullmatch(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                v,
            )
        ),
        "account": is_likely_account_number,
        "routing": is_likely_routing_number,
        "sort_code": is_likely_sort_code,
        "phone": is_likely_phone_number,
        "card": is_likely_card_number,
        "national_id": is_likely_national_id,
        "payment_handle": lambda v: bool(
            re.fullmatch(r"@[A-Za-z0-9._-]{2,30}", v)
        ),
        "long_reference": is_likely_reference,
        "address": is_likely_address,
    }

    validator = validators.get(category)
    return bool(validator(cleaned)) if validator else False
