"""Placing, viewing, cancelling, shipping and delivering orders."""
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BookUnavailable,
    CartNotFound,
    EmptyCart,
    InsufficientStock,
    OrderNotFound,
)
from app.models import NotificationType, Order, OrderItem, OrderStatus, OrderStatusChange
from app.patterns.order_observer import OrderEvent, order_events
from app.patterns.order_state import OrderLifecycle
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository


class OrderService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.orders = OrderRepository(session)
        self.carts = CartRepository(session)
        self.books = BookRepository(session)

    def place_order(self, user_id: int, shipping_address: str) -> Order:
        """Turn the cart into an order, all in one transaction.

        The cart, its items and the books are locked first, so stock cannot
        change between the check and the update. If any check fails, nothing
        is written: no order is created and the cart is left as it was.
        """
        cart = self.carts.lock_cart(user_id)
        if cart is None:
            raise CartNotFound()
        cart_items = self.carts.lock_items(cart.id)
        if not cart_items:
            raise EmptyCart()
        books = self.books.lock_many([item.book_id for item in cart_items])

        for item in cart_items:
            book = books[item.book_id]
            if not book.is_active:
                raise BookUnavailable(
                    f'"{book.title}" is no longer for sale. Please remove it from your cart.'
                )
            if item.quantity > book.stock:
                raise InsufficientStock(
                    f'Only {book.stock} of "{book.title}" left. Please reduce the quantity in your cart.'
                )

        order = Order(user_id=user_id, status=OrderStatus.PENDING, shipping_address=shipping_address)
        for item in cart_items:
            book = books[item.book_id]
            order.items.append(
                OrderItem(book_id=book.id, quantity=item.quantity, unit_price=book.price)
            )
            book.stock -= item.quantity
            self.session.delete(item)
        order.total_amount = sum((line.line_total for line in order.items), Decimal("0.00"))
        order.history.append(
            OrderStatusChange(
                from_status=None, to_status=OrderStatus.PENDING, changed_by=user_id, note="Order placed"
            )
        )
        self.orders.add(order)
        self.session.flush()  # gives the order its id, which the event needs
        order_events.publish(
            OrderEvent(
                type=NotificationType.ORDER_PLACED,
                order_id=order.id,
                customer_id=user_id,
                total=order.total_amount,
                actor_id=user_id,
            ),
            self.session,
        )
        self.session.commit()
        return self._reload(user_id, order.id)

    def list_orders(self, user_id: int, page: int, page_size: int) -> dict:
        items, total = self.orders.list_for_customer(user_id, page_size, (page - 1) * page_size)
        return _page(items, total, page, page_size)

    def get_order(self, user_id: int, order_id: int) -> Order:
        order = self.orders.get_for_customer(order_id, user_id)
        if order is None:
            raise OrderNotFound()
        return order

    def cancel_as_customer(self, user_id: int, order_id: int) -> Order:
        order = self.orders.lock_for_customer(order_id, user_id)
        if order is None:
            raise OrderNotFound()
        OrderLifecycle(order, self.session).cancel(user_id, "Cancelled by customer")
        self.session.commit()
        return self._reload(user_id, order_id)

    # --- Admin ------------------------------------------------------------

    def list_all_orders(self, status: OrderStatus | None, page: int, page_size: int) -> dict:
        items, total = self.orders.list_all(status, page_size, (page - 1) * page_size)
        return _page(items, total, page, page_size)

    def get_any_order(self, order_id: int) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise OrderNotFound()
        return order

    def ship(self, admin_id: int, order_id: int) -> Order:
        return self._admin_action(order_id, lambda lifecycle: lifecycle.ship(admin_id))

    def deliver(self, admin_id: int, order_id: int) -> Order:
        return self._admin_action(order_id, lambda lifecycle: lifecycle.deliver(admin_id))

    def cancel_as_admin(self, admin_id: int, order_id: int) -> Order:
        return self._admin_action(
            order_id, lambda lifecycle: lifecycle.cancel(admin_id, "Cancelled by the store")
        )

    def _admin_action(self, order_id: int, action: Callable[[OrderLifecycle], None]) -> Order:
        # Locking the order means a customer cancelling and an admin shipping
        # at the same moment are handled one after the other. The second one
        # then sees the new status and is refused if it no longer applies.
        order = self.orders.lock(order_id)
        if order is None:
            raise OrderNotFound()
        action(OrderLifecycle(order, self.session))
        self.session.commit()
        self.session.expire_all()
        return self.get_any_order(order_id)

    def _reload(self, user_id: int, order_id: int) -> Order:
        self.session.expire_all()
        return self.get_order(user_id, order_id)


def _page(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
