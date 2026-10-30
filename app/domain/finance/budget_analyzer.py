
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.domain.finance.transaction_parser import Transaction


def analyze_budget(transactions: list[Transaction]) -> dict[str, Any]:
    """Calculate financial summaries from locally parsed transactions.

    Amounts are grouped by currency. Unknown transaction types are not
    silently classified as income or expenses.
    """
    if not transactions:
        return {
            "status": "insufficient_data",
            "message": "No clearly identifiable transactions were found.",
            "transaction_count": 0,
            "currencies": {},
            "limitations": [
                "The parser could not identify reliable transaction rows."
            ],
        }

    summaries: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "income": Decimal("0"),
            "expenses": Decimal("0"),
            "unknown": Decimal("0"),
            "transaction_count": 0,
        }
    )

    for transaction in transactions:
        currency = transaction.currency or "UNSPECIFIED"
        summary = summaries[currency]
        summary["transaction_count"] += 1

        amount = abs(transaction.amount)

        if transaction.transaction_type == "income":
            summary["income"] += amount
        elif transaction.transaction_type == "expense":
            summary["expenses"] += amount
        else:
            summary["unknown"] += amount

    currencies: dict[str, dict[str, Any]] = {}

    for currency, summary in summaries.items():
        income = summary["income"]
        expenses = summary["expenses"]

        currencies[currency] = {
            "income": str(income),
            "expenses": str(expenses),
            "net": str(income - expenses),
            "unknown_amount": str(summary["unknown"]),
            "transaction_count": summary["transaction_count"],
        }

    return {
        "status": "success",
        "transaction_count": len(transactions),
        "currencies": currencies,
        "limitations": [
            "Income and expenses are classified using transaction descriptions "
            "and explicit debit/credit columns.",
            "Unclassified transactions are reported separately.",
            "Different currencies are never combined.",
            "These figures cover only transactions identified by the parser; "
            "they may not represent a complete financial statement.",
            "This report does not infer spending categories or monthly budgets.",
        ],
    }
