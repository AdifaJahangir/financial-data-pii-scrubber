
from app.domain.pii.detectors import find_sensitive_matches


def test_detector_finds_email():
    result = find_sensitive_matches(
        "Contact: sample@example.com"
    )

    assert any(category == "email" for category, _ in result)


def test_detector_finds_iban():
    result = find_sensitive_matches(
        "IBAN: GB82WEST12345698765432"
    )

    assert any(category == "iban" for category, _ in result)


def test_detector_finds_international_phone():
    result = find_sensitive_matches(
        "Phone: +1 415-555-0182"
    )

    assert any(category == "phone" for category, _ in result)


def test_detector_finds_labelled_account():
    result = find_sensitive_matches(
        "Account No: 123456789012"
    )

    assert any(
        category == "labelled_identifier"
        for category, _ in result
    )


def test_detector_finds_transaction_reference():
    result = find_sensitive_matches(
        "Transaction ID: ABC123456789012345"
    )

    assert any(
        category == "labelled_identifier"
        for category, _ in result
    )


def test_detector_preserves_safe_financial_information():
    content = (
        "Merchant: Netflix.com\n"
        "Date: 2026-04-15\n"
        "Amount: USD 42.00\n"
        "Balance: USD 500.00\n"
        "Order number: 987654321098\n"
    )

    assert find_sensitive_matches(content) == []


def test_detector_does_not_return_matched_sensitive_values():
    result = find_sensitive_matches(
        "Email: sample@example.com"
    )

    for category, value in result:
        assert value == "[POTENTIAL_IDENTIFIER]"
        assert "sample@example.com" not in value


def test_detector_finds_pakistani_cnic():
    matches = find_sensitive_matches(
        "CNIC: 35202-1234567-1"
    )

    assert any(category == "cnic" for category, _ in matches)


def test_detector_finds_pakistani_phone():
    matches = find_sensitive_matches(
        "Phone: 03001234567"
    )

    assert any(
        category == "pakistani_phone"
        for category, _ in matches
    )


def test_detector_finds_bsb_label():
    matches = find_sensitive_matches(
        "BSB: 123-456"
    )

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_preserves_safe_financial_values():
    content = (
        "Merchant: Netflix.com\n"
        "Date: 2026-10-29\n"
        "Amount: PKR 2,500.00\n"
        "Balance: PKR 15,000.00\n"
        "Order number: 987654321098\n"
    )

    assert find_sensitive_matches(content) == []


# Additional CSV and structured-row tests.


def test_detector_finds_account_number_inside_csv_row():
    content = (
        "Account No,Type,Balance\n"
        "123456789012,Savings,5000.00"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_card_number_inside_csv_row():
    content = (
        "Card Number,Type,Status\n"
        "4111111111111111,Debit,Active"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_routing_number_inside_csv_row():
    content = (
        "Routing Number,Bank,Country\n"
        "123456789,Example Bank,US"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_swift_inside_csv_row():
    content = (
        "SWIFT,Bank,Country\n"
        "ABCDUS12,Example Bank,US"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_ifsc_inside_csv_row():
    content = (
        "IFSC,Bank,Country\n"
        "ABCD0123456,Example Bank,IN"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_national_id_inside_csv_row():
    content = (
        "National ID,Country,Status\n"
        "AB123456789,Example,Active"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_wallet_id_inside_csv_row():
    content = (
        "Wallet ID,Provider,Status\n"
        "WALLET12345,Example,Active"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_consumer_number_inside_csv_row():
    content = (
        "Consumer Number,Provider,Amount\n"
        "123456789012,Utility,1000.00"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_finds_transaction_reference_inside_csv_row():
    content = (
        "Transaction ID,Date,Amount\n"
        "ABC123456789012345,2026-10-29,500.00"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )


def test_detector_preserves_safe_csv_financial_values():
    content = (
        "Merchant,Date,Amount,Balance,Order Number\n"
        "Netflix.com,2026-10-29,2500.00,15000.00,987654321098"
    )

    assert find_sensitive_matches(content) == []
def test_detector_finds_account_number_in_csv_metadata():
    content = (
        "Account Number,123456789012\n"
        "Date,Description,Amount,Balance\n"
        "2026-10-20,Grocery Store,45.00,955.00"
    )

    matches = find_sensitive_matches(content)

    assert any(
        category == "labelled_identifier"
        for category, _ in matches
    )