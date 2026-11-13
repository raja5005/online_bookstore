"""Order, payment and status-history models."""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.book import Book
from app.models.user import User


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, enum.Enum):
    CREDIT_CARD = "CREDIT_CARD"
    PAYPAL = "PAYPAL"
    BANK_TRANSFER = "BANK_TRANSFER"


class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class OrderItem(Base):
    """unit_price is copied from the book when the order is placed."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    book: Mapped[Book] = relationship()

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class Payment(Base):
    """One row per attempt. Card numbers and other payment details are never stored."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    transaction_ref: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class OrderStatusChange(Base):
    """A row in order_status_history. changed_by is None for automatic changes."""

    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[Optional[OrderStatus]] = mapped_column(Enum(OrderStatus))
    to_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus))
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    note: Mapped[Optional[str]] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    shipping_address: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    customer: Mapped[User] = relationship()
    items: Mapped[list[OrderItem]] = relationship(order_by=OrderItem.id, cascade="all")
    payments: Mapped[list[Payment]] = relationship(order_by=Payment.id, cascade="all")
    history: Mapped[list[OrderStatusChange]] = relationship(
        order_by=OrderStatusChange.id, cascade="all"
    )

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    def change_status(self, new_status: "OrderStatus", changed_by: int | None, note: str) -> None:
        """Set the status and record it in the history.

        Call this only through OrderLifecycle (app/patterns/order_state.py), which
        checks that the change is allowed.
        """
        self.history.append(
            OrderStatusChange(
                from_status=self.status, to_status=new_status, changed_by=changed_by, note=note
            )
        )
        self.status = new_status
