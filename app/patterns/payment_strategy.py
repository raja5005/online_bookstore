"""Strategy pattern: payment methods.

Each payment method is a separate strategy class with the same interface, pay().
The checkout code does not know or care which method the customer chose. It
hands the order total to whichever strategy matches, and gets back a
PaymentResult.

All three methods are simulated. Nothing is sent to a real payment provider,
and the details entered are never stored. Each method has a documented way to
trigger a failure, so failed payments can be demonstrated:

    Method          Accepted when                               Declined when
    Credit card     Valid card number that has not expired      4000 0000 0000 0002
    PayPal          Any valid email address                     The email starts with "declined@"
    Bank transfer   Valid routing number, 4-17 digit account    The account number ends in 0000

Adding a method means writing one new strategy class and registering it in
PAYMENT_STRATEGIES. Nothing else changes.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models import PaymentMethod
from app.schemas.payment import BankTransferDetails, CardDetails, PayPalDetails

DECLINED_TEST_CARD = "4000000000000002"


@dataclass(frozen=True)
class PaymentResult:
    succeeded: bool
    transaction_ref: str | None = None
    failure_reason: str | None = None


class PaymentStrategy(ABC):
    reference_prefix: str

    def pay(self, amount: Decimal, details) -> PaymentResult:
        problem = self._find_problem(amount, details)
        if problem:
            return PaymentResult(succeeded=False, failure_reason=problem)
        reference = f"{self.reference_prefix}-{uuid.uuid4().hex[:12].upper()}"
        return PaymentResult(succeeded=True, transaction_ref=reference)

    @abstractmethod
    def _find_problem(self, amount: Decimal, details) -> str | None:
        """Return why the payment is refused, or None to accept it."""


class CreditCardPayment(PaymentStrategy):
    reference_prefix = "CARD"

    def _find_problem(self, amount: Decimal, details: CardDetails) -> str | None:
        if not passes_luhn_check(details.card_number):
            return "The card number is not valid."
        today = date.today()
        if (details.expiry_year, details.expiry_month) < (today.year, today.month):
            return "The card has expired."
        if details.card_number == DECLINED_TEST_CARD:
            return "The card was declined by the issuer."
        return None


class PayPalPayment(PaymentStrategy):
    reference_prefix = "PAYPAL"

    def _find_problem(self, amount: Decimal, details: PayPalDetails) -> str | None:
        if details.paypal_email.lower().startswith("declined@"):
            return "PayPal declined the payment."
        return None


class BankTransferPayment(PaymentStrategy):
    reference_prefix = "BANK"

    def _find_problem(self, amount: Decimal, details: BankTransferDetails) -> str | None:
        if not is_valid_routing_number(details.routing_number):
            return "The routing number is not valid."
        if details.account_number.endswith("0000"):
            return "The bank reported insufficient funds."
        return None


PAYMENT_STRATEGIES: dict[PaymentMethod, PaymentStrategy] = {
    PaymentMethod.CREDIT_CARD: CreditCardPayment(),
    PaymentMethod.PAYPAL: PayPalPayment(),
    PaymentMethod.BANK_TRANSFER: BankTransferPayment(),
}


class PaymentProcessor:
    """The Strategy pattern's context: it runs whichever strategy it is given."""

    def __init__(self, strategy: PaymentStrategy) -> None:
        self.strategy = strategy

    @classmethod
    def for_method(cls, method: PaymentMethod) -> "PaymentProcessor":
        return cls(PAYMENT_STRATEGIES[method])

    def charge(self, amount: Decimal, details) -> PaymentResult:
        return self.strategy.pay(amount, details)


def passes_luhn_check(number: str) -> bool:
    """The checksum that every real card number satisfies."""
    total = 0
    for position, char in enumerate(reversed(number)):
        digit = int(char)
        if position % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def is_valid_routing_number(number: str) -> bool:
    """The checksum that every US bank routing number satisfies."""
    d = [int(char) for char in number]
    checksum = 3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])
    return checksum % 10 == 0
