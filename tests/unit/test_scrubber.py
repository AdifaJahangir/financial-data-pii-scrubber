from __future__ import annotations

from app.domain.pii.scrubber import scrub_document_text


def test_scrubber_removes_sensitive_identifiers_but_preserves_safe_data() -> None:
    content = (
        "Customer: Jane Doe\n"
        "Email: jane@example.com\n"
        "Phone: +1 415-555-0182\n"
        "IBAN: GB82WEST12345698765432\n"
        "Account: 1234567890\n"
        "Description: Netflix.com monthly charge\n"
        "Date: 2024-03-17\n"
        "Amount: $15.99\n"
        "Balance: $1,250.00\n"
        "Merchant: Amazon\n"
        "Address: 45 Maple Street, London\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "Jane Doe" in result.text
    assert "Netflix.com" in result.text
    assert "2024-03-17" in result.text
    assert "$15.99" in result.text
    assert "$1,250.00" in result.text
    assert "jane@example.com" not in result.text
    assert "415-555-0182" not in result.text
    assert "GB82WEST12345698765432" not in result.text
    assert "1234567890" not in result.text
    assert "45 Maple Street" not in result.text


def test_scrubber_handles_lowercase_and_spaced_iban_variants() -> None:
    content = "IBAN: gb82 west 1234 5678 9012 34\nDate: 2024-05-01\nAmount: €2,340.00\n"

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "2024-05-01" in result.text
    assert "€2,340.00" in result.text
    assert "gb82" not in result.text.lower()
    assert "west" not in result.text.lower()


def test_scrubber_fails_closed_for_empty_or_invalid_input() -> None:
    result = scrub_document_text("")

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_preserves_mixed_transaction_descriptions() -> None:
    content = (
        "Transaction: Card payment at Starbucks, 04/21/2024, amount 8.50 GBP, balance 280.30 GBP\n"
        "Reference: 123456789012\n"
        "Merchant: PayPal\n"
    )

    result = scrub_document_text(content)

    assert "Starbucks" in result.text
    assert "04/21/2024" in result.text
    assert "8.50 GBP" in result.text
    assert "280.30 GBP" in result.text
    assert "PayPal" in result.text
    assert "123456789012" not in result.text


def test_scrubber_keeps_generic_long_numeric_values_without_sensitive_labels() -> None:
    content = "Order number: 987654321098\nAmount: USD 42.00\nBalance: USD 500.00\nMerchant: Shopify\n"

    result = scrub_document_text(content)

    assert "987654321098" in result.text
    assert "USD 42.00" in result.text
    assert "USD 500.00" in result.text
    assert "Shopify" in result.text
