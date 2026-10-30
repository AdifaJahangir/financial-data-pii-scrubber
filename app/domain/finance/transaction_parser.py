
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Transaction:
    date: date | None
    description: str
    amount: Decimal
    currency: str | None = None
    transaction_type: str = "unknown"


DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d %B %Y",
)

AMOUNT_PATTERN = re.compile(
    r"(?P<currency>PKR|USD|EUR|GBP|INR|AED|SAR|Rs\.?|[$€£])?\s*"
    r"(?P<amount>-?\d[\d,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b"
)

CURRENCY_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "rs": "PKR",
    "rs.": "PKR",
}

BALANCE_LABELS = (
    "balance",
    "closing balance",
    "opening balance",
    "available balance",
    "current balance",
    "running balance",
    "previous balance",
    "new balance",
)


def _is_balance_description(description: str) -> bool:
    """Identify balance-only lines or rows, not actual transactions."""
    normalized = re.sub(r"^\W+", "", description.lower()).strip()

    return any(
        normalized == label or normalized.startswith(label + ":")
        or normalized.startswith(label + " ")
        for label in BALANCE_LABELS
    )


def _parse_date(value: str) -> date | None:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> Decimal | None:
    try:
        amount = Decimal(value.replace(",", ""))
        if not amount.is_finite():
            return None
        return amount
    except InvalidOperation:
        return None


def _currency(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().upper()
    return CURRENCY_MAP.get(normalized.lower(), normalized)


def _transaction_type(description: str, amount: Decimal) -> str:
    text = description.lower()

    if any(word in text for word in ("salary", "deposit", "refund", "credit")):
        return "income"

    if any(word in text for word in ("withdrawal", "payment", "purchase", "debit")):
        return "expense"

    if amount < 0:
        return "expense"

    return "unknown"


def _parse_csv(text: str) -> list[Transaction]:
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return []

    columns = {
        name.strip().lower(): name
        for name in reader.fieldnames
        if name
    }

    date_column = next(
        (columns[name] for name in ("date", "transaction date", "posting date")
         if name in columns),
        None,
    )

    description_column = next(
        (columns[name] for name in ("description", "transaction", "details", "merchant")
         if name in columns),
        None,
    )

    amount_column = next(
        (columns[name] for name in ("amount", "transaction amount")
         if name in columns),
        None,
    )

    debit_column = next(
        (columns[name] for name in ("debit", "withdrawal", "money out")
         if name in columns),
        None,
    )

    credit_column = next(
        (columns[name] for name in ("credit", "deposit", "money in")
         if name in columns),
        None,
    )

    currency_column = next(
        (columns[name] for name in ("currency",)
         if name in columns),
        None,
    )

    if not description_column or not (
        amount_column or debit_column or credit_column
    ):
        return []

    transactions = []

    for row in reader:
        description = (row.get(description_column) or "").strip()

        if not description or _is_balance_description(description):
            continue

        raw_amount = (
            (row.get(amount_column) or "").strip()
            if amount_column else ""
        )

        transaction_type = "unknown"

        if raw_amount:
            amount = _parse_amount(raw_amount)
        else:
            debit = (
                _parse_amount((row.get(debit_column) or "").strip())
                if debit_column else None
            )

            credit = (
                _parse_amount((row.get(credit_column) or "").strip())
                if credit_column else None
            )

            if debit is not None and debit != 0:
                amount = -abs(debit)
                transaction_type = "expense"
            elif credit is not None and credit != 0:
                amount = abs(credit)
                transaction_type = "income"
            else:
                amount = None

        if amount is None:
            continue

        raw_date = (
            (row.get(date_column) or "").strip()
            if date_column else ""
        )

        parsed_date = _parse_date(raw_date) if raw_date else None

        currency = (
            (row.get(currency_column) or "").strip()
            if currency_column else None
        )

        if transaction_type == "unknown":
            transaction_type = _transaction_type(description, amount)

        transactions.append(
            Transaction(
                date=parsed_date,
                description=description,
                amount=amount,
                currency=_currency(currency),
                transaction_type=transaction_type,
            )
        )

    return transactions


def parse_transactions(
    document_text: str,
    filename: str = "",
) -> list[Transaction]:
    """Extract clearly identifiable transactions from scrubbed document text."""

    if not document_text or not document_text.strip():
        return []

    if filename.lower().endswith(".csv"):
        try:
            return _parse_csv(document_text)
        except (csv.Error, ValueError):
            return []

    transactions = []
    lines = [
        line.strip()
        for line in document_text.splitlines()
        if line.strip()
    ]

    pending_date = None
    previous_description = ""

    for line in lines:
        if line.startswith("==="):
            continue

        # Never interpret account balances as transactions.
        if _is_balance_description(line):
            continue

        date_match = DATE_PATTERN.search(line)

        if date_match and line.lower().startswith("date"):
            pending_date = _parse_date(date_match.group())
            continue

        amount_matches = list(AMOUNT_PATTERN.finditer(line))

        if not amount_matches:
            if not line.lower().startswith(("date:", "amount:", "balance:")):
                previous_description = line
            continue

        if any(
            word in line.lower()
            for word in (
                "reference",
                "account",
                "iban",
                "trace",
                "transaction id",
            )
        ):
            continue

        if len(amount_matches) != 1:
            continue

        amount_match = amount_matches[0]
        amount = _parse_amount(amount_match.group("amount"))

        if amount is None:
            continue

        parsed_date = (
            _parse_date(date_match.group())
            if date_match
            else pending_date
        )

        description = line

        if date_match:
            description = description.replace(date_match.group(), " ")

        description = description.replace(amount_match.group(), " ")
        description = re.sub(r"\s+", " ", description).strip(" ,:-")

        if description.lower().rstrip(":") in (
            "amount",
            "balance",
            "date",
        ):
            description = previous_description

        if not description or _is_balance_description(description):
            continue

        lower_description = description.lower()

        transaction_words = (
            "payment",
            "purchase",
            "grocery",
            "salary",
            "deposit",
            "withdrawal",
            "refund",
            "credit",
            "debit",
            "bill",
            "transfer",
            "shopping",
            "utility",
        )

        has_currency = bool(amount_match.group("currency"))

        has_transaction_word = any(
            word in lower_description
            for word in transaction_words
        )

        if not (has_currency or has_transaction_word):
            continue

        currency = _currency(amount_match.group("currency"))

        transactions.append(
            Transaction(
                date=parsed_date,
                description=description,
                amount=amount,
                currency=currency,
                transaction_type=_transaction_type(
                    description,
                    amount,
                ),
            )
        )

        pending_date = None

    return transactions
