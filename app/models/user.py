"""User models.

Customer and Admin are stored in the single `users` table. SQLAlchemy reads the
`role` column to decide which class each row becomes.
"""
import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.cart import Cart


class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __mapper_args__ = {"polymorphic_on": "role", "polymorphic_abstract": True}


class Customer(User):
    cart: Mapped[Optional["Cart"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"polymorphic_identity": UserRole.CUSTOMER}


class Admin(User):
    __mapper_args__ = {"polymorphic_identity": UserRole.ADMIN}
