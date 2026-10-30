
from app.domain.pii.scrubber import scrub_document_text


def test_scrubber_redacts_unformatted_cnic() -> None:
    result = scrub_document_text("CNIC Number: 3520212345671")

    assert result.safe_to_send is True
    assert "[REDACTED_CNIC]" in result.text
    assert "3520212345671" not in result.text


def test_scrubber_redacts_consumer_no_variant() -> None:
    result = scrub_document_text(
        "Consumer No: 123456789012"
    )

    assert result.safe_to_send is True
    assert "[REDACTED_CONSUMER_NUMBER]" in result.text
    assert "123456789012" not in result.text


def test_scrubber_redacts_consumer_id_variant() -> None:
    result = scrub_document_text(
        "Consumer ID: ELEC123456789"
    )

    assert result.safe_to_send is True
    assert "[REDACTED_CONSUMER_NUMBER]" in result.text
    assert "ELEC123456789" not in result.text


def test_scrubber_redacts_wallet_number_variant() -> None:
    result = scrub_document_text(
        "Wallet Number: WALLET123456"
    )

    assert result.safe_to_send is True
    assert "[REDACTED_WALLET_ID]" in result.text
    assert "WALLET123456" not in result.text


def test_scrubber_redacts_wallet_no_variant() -> None:
    result = scrub_document_text(
        "Wallet No: WALLET123456"
    )

    assert result.safe_to_send is True
    assert "[REDACTED_WALLET_ID]" in result.text
    assert "WALLET123456" not in result.text


def test_scrubber_preserves_safe_financial_values() -> None:
    content = (
        "Merchant: Netflix.com\n"
        "Order Number: 987654321098\n"
        "Date: 2026-04-15\n"
        "Amount: PKR 2,500.00\n"
        "Balance: PKR 15,000.00\n"
    )

    result = scrub_document_text(content)

    assert result.safe_to_send is True
    assert "Netflix.com" in result.text
    assert "987654321098" in result.text
    assert "2026-04-15" in result.text
    assert "PKR 2,500.00" in result.text
    assert "PKR 15,000.00" in result.text
