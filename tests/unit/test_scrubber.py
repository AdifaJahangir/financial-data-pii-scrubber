
from __future__ import annotations

from unittest.mock import patch

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
    content = (
        "IBAN: gb82 west 1234 5678 9012 34\n"
        "Date: 2024-05-01\n"
        "Amount: €2,340.00\n"
    )

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
        "Transaction: Card payment at Starbucks, 04/21/2024, "
        "amount 8.50 GBP, balance 280.30 GBP\n"
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
    content = (
        "Order number: 987654321098\n"
        "Amount: USD 42.00\n"
        "Balance: USD 500.00\n"
        "Merchant: Shopify\n"
    )

    result = scrub_document_text(content)

    assert "987654321098" in result.text
    assert "USD 42.00" in result.text
    assert "USD 500.00" in result.text
    assert "Shopify" in result.text


def test_scrubber_redacts_labelled_upi_id() -> None:
    result = scrub_document_text("UPI ID: sample@upi")

    assert result.safe_to_send is True
    assert result.redacted_count == 1
    assert "[REDACTED_HANDLE]" in result.text
    assert "sample@upi" not in result.text


def test_scrubber_rejects_malformed_email() -> None:
    result = scrub_document_text("Email: sample@invalid")

    assert result.safe_to_send is False
    assert result.text == ""
    assert any(
        "Malformed email" in warning
        for warning in result.warnings
    )


def test_scrubber_redacts_international_national_id_formats() -> None:
    content = (
        "Aadhaar: 1234-5678-9012\n"
        "PAN: ABCDE1234F\n"
        "SIN: 046454286\n"
        "NI Number: AB123456C\n"
        "Date: 2026-04-01\n"
        "Amount: $250.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "1234-5678-9012" not in result.text
    assert "ABCDE1234F" not in result.text
    assert "046454286" not in result.text
    assert "AB123456C" not in result.text
    assert "2026-04-01" in result.text
    assert "$250.00" in result.text


def test_scrubber_redacts_account_number_label_variants() -> None:
    content = (
        "A/C No: 123456789012\n"
        "ACC: 987654321098\n"
        "Account No: 112233445566\n"
        "Merchant: Amazon\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "123456789012" not in result.text
    assert "987654321098" not in result.text
    assert "112233445566" not in result.text
    assert "Amazon" in result.text


def test_scrubber_redacts_transaction_identifiers() -> None:
    content = (
        "Transaction ID: ABC123456789012345\n"
        "Trace: 123456789012\n"
        "UTR: N091260044556677\n"
        "Merchant: Starbucks\n"
        "Amount: PKR 500.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "ABC123456789012345" not in result.text
    assert "123456789012" not in result.text
    assert "N091260044556677" not in result.text
    assert "Starbucks" in result.text
    assert "PKR 500.00" in result.text


def test_scrubber_preserves_merchant_domains_and_safe_order_numbers() -> None:
    content = (
        "Merchant: Netflix.com\n"
        "Merchant: Amazon.co.uk\n"
        "Order number: 987654321098\n"
        "Date: 2026-04-15\n"
        "Amount: USD 42.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "Netflix.com" in result.text
    assert "Amazon.co.uk" in result.text
    assert "987654321098" in result.text
    assert "2026-04-15" in result.text
    assert "USD 42.00" in result.text


def test_scrubber_redacts_identifiers_inside_transaction_descriptions() -> None:
    content = (
        "Transaction: Payment to merchant, "
        "Transaction ID: ABC123456789012345\n"
        "Transaction: Mobile top-up, "
        "Phone: +1 415-555-0182\n"
        "Merchant: Foodpanda\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "ABC123456789012345" not in result.text
    assert "415-555-0182" not in result.text
    assert "Foodpanda" in result.text


def test_scrubber_fails_closed_when_independent_detector_finds_residual():
    with patch(
        "app.domain.pii.scrubber.find_sensitive_matches",
        return_value=[
            ("test_identifier", "[POTENTIAL_IDENTIFIER]")
        ],
    ):
        result = scrub_document_text(
            "Merchant: Netflix.com\nAmount: USD 10.00"
        )

    assert result.safe_to_send is False
    assert result.text == ""
    assert any(
        "Independent safety validation" in warning
        for warning in result.warnings
    )


def test_scrubber_fails_closed_for_pakistani_address_format() -> None:
    content = (
        "Customer: Jane Doe\n"
        "Address: House 12, Street 5, G-10, Islamabad\n"
        "Amount: PKR 2,500.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_fails_closed_for_address_without_street_number() -> None:
    content = (
        "Mailing Address: Gulberg III, Lahore, Pakistan\n"
        "Amount: PKR 1,200.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_fails_closed_for_labelled_postal_code() -> None:
    content = (
        "Postal Code: 38000\n"
        "Merchant: Amazon\n"
        "Amount: USD 25.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_redacts_cnic_if_detected() -> None:
    content = (
        "CNIC: 35202-1234567-1\n"
        "Merchant: Foodpanda\n"
        "Amount: PKR 850.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "[REDACTED_CNIC]" in result.text
    assert "35202-1234567-1" not in result.text
    assert "Foodpanda" in result.text
    assert "PKR 850.00" in result.text


def test_scrubber_redacts_labelled_consumer_number() -> None:
    content = (
        "Consumer Number: 123456789012\n"
        "Merchant: Utility Provider\n"
        "Amount: PKR 3,000.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "[REDACTED_CONSUMER_NUMBER]" in result.text
    assert "123456789012" not in result.text
    assert "Utility Provider" in result.text
    assert "PKR 3,000.00" in result.text


def test_scrubber_redacts_labelled_wallet_id() -> None:
    content = (
        "Wallet ID: WALLET123456789\n"
        "Merchant: Online Store\n"
        "Amount: PKR 500.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "[REDACTED_WALLET_ID]" in result.text
    assert "WALLET123456789" not in result.text
    assert "Online Store" in result.text
    assert "PKR 500.00" in result.text


def test_scrubber_redacts_pakistani_cnic() -> None:
    result = scrub_document_text("CNIC: 35202-1234567-1")

    assert result.safe_to_send is True
    assert result.text == "[REDACTED_CNIC]"
    assert "35202-1234567-1" not in result.text


def test_scrubber_redacts_pakistani_phone() -> None:
    result = scrub_document_text("Phone: 03001234567")

    assert result.safe_to_send is True
    assert "[REDACTED_PHONE]" in result.text
    assert "03001234567" not in result.text


def test_scrubber_redacts_consumer_number() -> None:
    result = scrub_document_text(
        "Consumer Number: 123456789012"
    )

    assert result.safe_to_send is True
    assert result.text == "[REDACTED_CONSUMER_NUMBER]"
    assert "123456789012" not in result.text


def test_scrubber_redacts_wallet_id() -> None:
    result = scrub_document_text("Wallet ID: WALLET123456")

    assert result.safe_to_send is True
    assert result.text == "[REDACTED_WALLET_ID]"
    assert "WALLET123456" not in result.text


def test_scrubber_redacts_valid_card_number() -> None:
    result = scrub_document_text(
        "Card Number: 4111111111111111"
    )

    assert result.safe_to_send is True
    assert "[REDACTED_CARD]" in result.text
    assert "4111111111111111" not in result.text
