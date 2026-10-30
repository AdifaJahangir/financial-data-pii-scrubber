from app.domain.pii.validation import (
    is_likely_card_number,
    is_likely_pakistani_phone,
    is_likely_cnic,
    is_likely_sort_code,
    is_likely_consumer_number,
    is_likely_wallet_id,
)


def test_valid_luhn_card_number():
    assert is_likely_card_number("4111111111111111") is True


def test_invalid_luhn_card_number():
    assert is_likely_card_number("4111111111111112") is False


def test_valid_pakistani_phone():
    assert is_likely_pakistani_phone("03001234567") is True


def test_valid_international_pakistani_phone():
    assert is_likely_pakistani_phone("923001234567") is True


def test_invalid_pakistani_phone():
    assert is_likely_pakistani_phone("12345678901") is False


def test_formatted_cnic():
    assert is_likely_cnic("35202-1234567-1") is True


def test_unformatted_cnic():
    assert is_likely_cnic("3520212345671") is True


def test_invalid_cnic_length():
    assert is_likely_cnic("123456789") is False


def test_valid_sort_code():
    assert is_likely_sort_code("12-34-56") is True


def test_valid_spaced_sort_code():
    assert is_likely_sort_code("12 34 56") is True


def test_invalid_sort_code():
    assert is_likely_sort_code("12345") is False


def test_valid_consumer_number():
    assert is_likely_consumer_number("123456789012") is True


def test_invalid_consumer_number():
    assert is_likely_consumer_number("ABCDEF") is False


def test_valid_wallet_id():
    assert is_likely_wallet_id("WALLET123456") is True


def test_invalid_wallet_id():
    assert is_likely_wallet_id("WALLET") is False