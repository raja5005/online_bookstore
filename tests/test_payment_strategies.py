"""Strategy pattern: each payment method's own rules, behind one interface."""
from datetime import date
from decimal import Decimal

import pytest

from app.models import PaymentMethod
from app.patterns.payment_strategy import (
    BankTransferPayment,
    CreditCardPayment,
    PaymentProcessor,
    PaymentResult,
    PaymentStrategy,
    PayPalPayment,
    is_valid_routing_number,
    passes_luhn_check,
)
from app.schemas.payment import BankTransferDetails, CardDetails, PayPalDetails

AMOUNT = Decimal("25.00")
VALID_CARD = "4242424242424242"
DECLINED_CARD = "4000000000000002"
VALID_ROUTING = "011000015"


def card(**changes) -> CardDetails:
    values = {
        "method": "CREDIT_CARD",
        "cardholder_name": "Pat Doe",
        "card_number": VALID_CARD,
        "expiry_month": 12,
        "expiry_year": date.today().year + 2,
        "cvv": "123",
    }
    return CardDetails(**{**values, **changes})


def paypal(email="buyer@example.com") -> PayPalDetails:
    return PayPalDetails(method="PAYPAL", paypal_email=email)


def bank(**changes) -> BankTransferDetails:
    values = {
        "method": "BANK_TRANSFER",
        "account_name": "Pat Doe",
        "routing_number": VALID_ROUTING,
        "account_number": "12345678",
    }
    return BankTransferDetails(**{**values, **changes})


def last_month() -> tuple[int, int]:
    today = date.today()
    return (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)


# --- Checksums ------------------------------------------------------------


@pytest.mark.parametrize(
    ("number", "valid"),
    [(VALID_CARD, True), (DECLINED_CARD, True), ("4242424242424241", False), ("79927398713", True)],
)
def test_luhn_check(number, valid):
    assert passes_luhn_check(number) is valid


@pytest.mark.parametrize(("number", "valid"), [(VALID_ROUTING, True), ("011000016", False), ("021000021", True)])
def test_routing_number_check(number, valid):
    assert is_valid_routing_number(number) is valid


# --- Credit card ----------------------------------------------------------


def test_card_payment_succeeds_with_a_reference():
    result = CreditCardPayment().pay(AMOUNT, card())
    assert result.succeeded
    assert result.transaction_ref.startswith("CARD-")
    assert result.failure_reason is None


def test_each_payment_gets_a_different_reference():
    strategy = CreditCardPayment()
    assert strategy.pay(AMOUNT, card()).transaction_ref != strategy.pay(AMOUNT, card()).transaction_ref


def test_card_number_with_spaces_is_accepted():
    assert CreditCardPayment().pay(AMOUNT, card(card_number="4242 4242 4242 4242")).succeeded


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"card_number": DECLINED_CARD}, "declined"),
        ({"card_number": "4242424242424241"}, "not valid"),
        (dict(zip(("expiry_year", "expiry_month"), last_month())), "expired"),
    ],
)
def test_card_payment_failures(changes, reason):
    result = CreditCardPayment().pay(AMOUNT, card(**changes))
    assert not result.succeeded
    assert reason in result.failure_reason
    assert result.transaction_ref is None


def test_card_expiring_this_month_is_still_valid():
    today = date.today()
    assert CreditCardPayment().pay(AMOUNT, card(expiry_year=today.year, expiry_month=today.month)).succeeded


# --- PayPal ---------------------------------------------------------------


def test_paypal_payment_succeeds():
    result = PayPalPayment().pay(AMOUNT, paypal())
    assert result.succeeded
    assert result.transaction_ref.startswith("PAYPAL-")


@pytest.mark.parametrize("email", ["declined@example.com", "Declined@Example.com"])
def test_paypal_declined_account(email):
    result = PayPalPayment().pay(AMOUNT, paypal(email))
    assert not result.succeeded
    assert "declined" in result.failure_reason


# --- Bank transfer --------------------------------------------------------


def test_bank_transfer_succeeds():
    result = BankTransferPayment().pay(AMOUNT, bank())
    assert result.succeeded
    assert result.transaction_ref.startswith("BANK-")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [({"routing_number": "011000016"}, "routing"), ({"account_number": "12340000"}, "insufficient")],
)
def test_bank_transfer_failures(changes, reason):
    result = BankTransferPayment().pay(AMOUNT, bank(**changes))
    assert not result.succeeded
    assert reason in result.failure_reason


# --- The pattern itself ---------------------------------------------------


@pytest.mark.parametrize(
    ("method", "strategy_class"),
    [
        (PaymentMethod.CREDIT_CARD, CreditCardPayment),
        (PaymentMethod.PAYPAL, PayPalPayment),
        (PaymentMethod.BANK_TRANSFER, BankTransferPayment),
    ],
)
def test_each_method_selects_its_strategy(method, strategy_class):
    assert isinstance(PaymentProcessor.for_method(method).strategy, strategy_class)


def test_every_method_has_a_strategy():
    for method in PaymentMethod:
        assert isinstance(PaymentProcessor.for_method(method).strategy, PaymentStrategy)


def test_processor_runs_any_strategy_it_is_given():
    class AlwaysApproves(PaymentStrategy):
        reference_prefix = "TEST"

        def _find_problem(self, amount, details):
            return None

    result = PaymentProcessor(AlwaysApproves()).charge(AMOUNT, details=None)
    assert isinstance(result, PaymentResult)
    assert result.transaction_ref.startswith("TEST-")
