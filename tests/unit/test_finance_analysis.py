
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.domain.finance.transaction_parser import parse_transactions
from app.domain.finance.budget_analyzer import analyze_budget
from app.api.routes.analysis import create_budget_analysis


def test_parse_synthetic_text_transactions():
    text = """
    Grocery Store Payment
    Date: 2026-10-20
    Amount: USD 45.00
    """

    transactions = parse_transactions(text)

    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("45.00")
    assert transactions[0].currency == "USD"
    assert transactions[0].date == date(2026, 10, 20)
    assert transactions[0].transaction_type == "expense"


def test_parse_synthetic_csv_transactions():
    text = """Date,Description,Debit,Credit,Currency
2026-10-20,Grocery Store,45.00,,USD
2026-10-21,Salary,,1500.00,USD
"""

    transactions = parse_transactions(text, "synthetic.csv")

    assert len(transactions) == 2
    assert transactions[0].transaction_type == "expense"
    assert transactions[0].amount == Decimal("-45.00")
    assert transactions[1].transaction_type == "income"
    assert transactions[1].amount == Decimal("1500.00")


def test_budget_analysis_calculates_totals_by_currency():
    text = """Date,Description,Debit,Credit,Currency
2026-10-20,Grocery Store,45.00,,USD
2026-10-21,Salary,,1500.00,USD
2026-10-22,Utility Bill,500.00,,PKR
"""

    transactions = parse_transactions(text, "synthetic.csv")
    result = analyze_budget(transactions)

    assert result["status"] == "success"
    assert result["transaction_count"] == 3

    assert result["currencies"]["USD"]["income"] == "1500.00"
    assert result["currencies"]["USD"]["expenses"] == "45.00"
    assert result["currencies"]["USD"]["net"] == "1455.00"

    assert result["currencies"]["PKR"]["expenses"] == "500.00"


def test_empty_input_returns_insufficient_data():
    result = analyze_budget([])

    assert result["status"] == "insufficient_data"
    assert result["transaction_count"] == 0


def test_ambiguous_text_is_not_guessed():
    text = "Transaction reference 123456789"
    transactions = parse_transactions(text)

    assert transactions == []


def test_api_budget_analysis_uses_scrubbed_csv_documents():
    csv_text = """Date,Description,Debit,Credit,Currency
2026-10-20,Grocery Store,45.00,,USD
2026-10-21,Salary,,1500.00,USD
"""

    document = SimpleNamespace(
        status="success",
        safe_to_send=True,
        warnings=None,
        scrubbed_output=csv_text,
        file_name="synthetic.csv",
    )

    job = SimpleNamespace(documents=[document])

    result = create_budget_analysis(job)

    assert result["status"] == "success"
    assert result["transaction_count"] == 2
    assert result["currencies"]["USD"]["income"] == "1500.00"
    assert result["currencies"]["USD"]["expenses"] == "45.00"
    assert result["currencies"]["USD"]["net"] == "1455.00"


def test_api_budget_analysis_skips_unsafe_documents():
    document = SimpleNamespace(
        status="success",
        safe_to_send=False,
        warnings=None,
        scrubbed_output=(
            "Grocery Store Payment\n"
            "Amount: USD 45.00"
        ),
        file_name="synthetic.txt",
    )

    job = SimpleNamespace(documents=[document])

    result = create_budget_analysis(job)

    assert result["status"] == "insufficient_data"
    assert result["transaction_count"] == 0


def test_api_budget_analysis_skips_documents_with_warnings():
    document = SimpleNamespace(
        status="success",
        safe_to_send=True,
        warnings="Potential sensitive information detected.",
        scrubbed_output=(
            "Grocery Store Payment\n"
            "Amount: USD 45.00"
        ),
        file_name="synthetic.txt",
    )

    job = SimpleNamespace(documents=[document])

    result = create_budget_analysis(job)

    assert result["status"] == "insufficient_data"
    assert result["transaction_count"] == 0


def test_api_budget_analysis_handles_empty_documents():
    job = SimpleNamespace(documents=[])

    result = create_budget_analysis(job)

    assert result["status"] == "insufficient_data"
    assert result["transaction_count"] == 0
