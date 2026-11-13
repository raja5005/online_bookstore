"""Payment request shapes. The `method` field decides which shape applies.

These check format only, such as "16 digits". Whether a payment is accepted,
for example whether a card has expired, is decided by its payment strategy.
"""
import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, StringConstraints

from app.schemas.order import OrderOut, PaymentOut


def _digits_only(value: object) -> object:
    return re.sub(r"[\s-]", "", value) if isinstance(value, str) else value


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CardDetails(BaseModel):
    method: Literal["CREDIT_CARD"]
    cardholder_name: Name
    card_number: Annotated[str, BeforeValidator(_digits_only), StringConstraints(pattern=r"^[0-9]{12,19}$")]
    expiry_month: Annotated[int, Field(ge=1, le=12)]
    expiry_year: Annotated[int, Field(ge=2000, le=2100)]
    cvv: Annotated[str, StringConstraints(pattern=r"^[0-9]{3,4}$")]


class PayPalDetails(BaseModel):
    method: Literal["PAYPAL"]
    paypal_email: EmailStr


class BankTransferDetails(BaseModel):
    method: Literal["BANK_TRANSFER"]
    account_name: Name
    routing_number: Annotated[str, BeforeValidator(_digits_only), StringConstraints(pattern=r"^[0-9]{9}$")]
    account_number: Annotated[str, BeforeValidator(_digits_only), StringConstraints(pattern=r"^[0-9]{4,17}$")]


PaymentDetails = Annotated[
    Union[CardDetails, PayPalDetails, BankTransferDetails], Field(discriminator="method")
]


class PaymentAttemptOut(BaseModel):
    """The recorded attempt, whether it succeeded or failed, and the updated order."""

    payment: PaymentOut
    order: OrderOut
