"""Request and response shapes for orders."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, computed_field

from app.models import OrderStatus, PaymentMethod, PaymentStatus
from app.patterns.order_state import state_for


class OrderCreate(BaseModel):
    shipping_address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class OrderBookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    authors: list[str]


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    book: OrderBookOut
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method: PaymentMethod
    amount: Decimal
    status: PaymentStatus
    transaction_ref: str | None
    failure_reason: str | None
    created_at: datetime


class StatusChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: OrderStatus | None
    to_status: OrderStatus
    note: str | None
    changed_at: datetime


class OrderSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    total_amount: Decimal
    item_count: int
    created_at: datetime

    @computed_field
    @property
    def available_actions(self) -> list[str]:
        """What the order's current state allows: pay, ship, deliver or cancel."""
        return list(state_for(self.status).actions)


class OrderOut(OrderSummaryOut):
    shipping_address: str
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    history: list[StatusChangeOut]


class OrderPage(BaseModel):
    items: list[OrderSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str


class AdminOrderSummaryOut(OrderSummaryOut):
    customer: CustomerOut


class AdminOrderOut(OrderOut):
    customer: CustomerOut


class AdminOrderPage(BaseModel):
    items: list[AdminOrderSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int
