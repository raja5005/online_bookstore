"""Importing this package registers every model with SQLAlchemy."""
from app.models.book import Author, Book, BookAuthor, Category
from app.models.cart import Cart, CartItem
from app.models.notification import Notification, NotificationType
from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusChange,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from app.models.user import Admin, Customer, User, UserRole

__all__ = [
    "Admin",
    "Author",
    "Book",
    "BookAuthor",
    "Cart",
    "CartItem",
    "Category",
    "Customer",
    "Notification",
    "NotificationType",
    "Order",
    "OrderItem",
    "OrderStatus",
    "OrderStatusChange",
    "Payment",
    "PaymentMethod",
    "PaymentStatus",
    "User",
    "UserRole",
]
