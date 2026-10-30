
from app.domain.pii.scrubber import scrub_document_text


def test_scrubber_fails_closed_for_incomplete_cnic() -> None:
    result = scrub_document_text("CNIC: 35202-12345")

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_fails_closed_for_incomplete_consumer_number() -> None:
    result = scrub_document_text("Consumer Number: 123")

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_fails_closed_for_incomplete_wallet_id() -> None:
    result = scrub_document_text("Wallet ID: WAL")

    assert result.safe_to_send is False
    assert result.text == ""
    assert result.warnings


def test_scrubber_preserves_unlabelled_order_reference() -> None:
    result = scrub_document_text(
        "Order Number: 987654321098\n"
        "Merchant: Amazon\n"
        "Amount: PKR 500.00"
    )

    assert result.safe_to_send is True
    assert "987654321098" in result.text
    assert "Amazon" in result.text
    assert "PKR 500.00" in result.text
