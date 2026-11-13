"""Shopping cart models."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.book import Book

if TYPE_CHECKING:
    from app.models.user import Customer


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    quantity: Mapped[int]
    added_at: Mapped[datetime] = mapped_column(server_default=func.now())

    book: Mapped[Book] = relationship()

    @property
    def line_total(self) -> Decimal:
        return self.book.price * self.quantity

    @property
    def available(self) -> bool:
        """False if the book was withdrawn, or stock fell after it was added."""
        return self.book.is_active and self.quantity <= self.book.stock


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="cart")
    items: Mapped[list[CartItem]] = relationship(
        order_by=CartItem.id, cascade="all, delete-orphan"
    )

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0.00"))

    @property
    def can_checkout(self) -> bool:
        return bool(self.items) and all(item.available for item in self.items)
