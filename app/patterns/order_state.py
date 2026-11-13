"""State pattern: the order lifecycle.

Each order status is a class that knows which actions are allowed in that
status and what each one does. OrderLifecycle, the context, hands every action
to the class for the order's current status. Code elsewhere never needs
`if status == ...` checks to know whether an order can ship or be cancelled.

    Status      Allowed actions    Result
    PENDING     pay                PAID
                cancel             CANCELLED, stock restored
    PAID        ship               SHIPPED
                cancel             CANCELLED, stock restored, payment refunded
    SHIPPED     deliver            DELIVERED
    DELIVERED   none (final)
    CANCELLED   none (final)

Any other action is refused with InvalidOrderTransition and changes nothing.
"""
import uuid
from abc import ABC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidOrderTransition
from app.models import NotificationType, Order, OrderStatus, Payment, PaymentStatus
from app.patterns.order_observer import OrderEvent, OrderEventPublisher, order_events
from app.repositories.book_repository import BookRepository

# The event announced when an order reaches each status (Observer pattern).
EVENT_FOR_STATUS = {
    OrderStatus.PAID: NotificationType.ORDER_PAID,
    OrderStatus.SHIPPED: NotificationType.ORDER_SHIPPED,
    OrderStatus.DELIVERED: NotificationType.ORDER_DELIVERED,
    OrderStatus.CANCELLED: NotificationType.ORDER_CANCELLED,
}


class OrderState(ABC):
    status: OrderStatus
    actions: tuple[str, ...] = ()

    def pay(self, order: "OrderLifecycle", note: str) -> None:
        self._refuse("paid")

    def ship(self, order: "OrderLifecycle", actor_id: int) -> None:
        self._refuse("shipped")

    def deliver(self, order: "OrderLifecycle", actor_id: int) -> None:
        self._refuse("delivered")

    def cancel(self, order: "OrderLifecycle", actor_id: int, note: str) -> None:
        self._refuse("cancelled")

    def _refuse(self, action: str) -> None:
        current = self.status.value.lower()
        if action == current:
            raise InvalidOrderTransition(f"This order has already been {action}.")
        article = "An" if current[0] in "aeiou" else "A"
        raise InvalidOrderTransition(f"{article} {current} order cannot be {action}.")


class PendingState(OrderState):
    status = OrderStatus.PENDING
    actions = ("pay", "cancel")

    def pay(self, order: "OrderLifecycle", note: str) -> None:
        order.move_to(OrderStatus.PAID, None, note)

    def cancel(self, order: "OrderLifecycle", actor_id: int, note: str) -> None:
        order.restore_stock()
        order.move_to(OrderStatus.CANCELLED, actor_id, note)


class PaidState(OrderState):
    status = OrderStatus.PAID
    actions = ("ship", "cancel")

    def ship(self, order: "OrderLifecycle", actor_id: int) -> None:
        order.move_to(OrderStatus.SHIPPED, actor_id, "Shipped")

    def cancel(self, order: "OrderLifecycle", actor_id: int, note: str) -> None:
        order.restore_stock()
        order.refund_payment()
        order.move_to(OrderStatus.CANCELLED, actor_id, f"{note}, payment refunded")


class ShippedState(OrderState):
    status = OrderStatus.SHIPPED
    actions = ("deliver",)

    def deliver(self, order: "OrderLifecycle", actor_id: int) -> None:
        order.move_to(OrderStatus.DELIVERED, actor_id, "Delivered")


class DeliveredState(OrderState):
    status = OrderStatus.DELIVERED


class CancelledState(OrderState):
    status = OrderStatus.CANCELLED


STATES: dict[OrderStatus, OrderState] = {
    state.status: state
    for state in (PendingState(), PaidState(), ShippedState(), DeliveredState(), CancelledState())
}


def state_for(status: OrderStatus) -> OrderState:
    return STATES[status]


class OrderLifecycle:
    """The State pattern's context. Every status change goes through move_to()."""

    def __init__(
        self, order: Order, session: Session, publisher: OrderEventPublisher | None = None
    ) -> None:
        self.order = order
        self.session = session
        self.publisher = publisher or order_events
        self._refunded = False

    @property
    def state(self) -> OrderState:
        return state_for(self.order.status)

    @property
    def actions(self) -> tuple[str, ...]:
        return self.state.actions

    # Actions: each one is handled by the current state.

    def pay(self, note: str) -> None:
        self.state.pay(self, note)

    def ship(self, actor_id: int) -> None:
        self.state.ship(self, actor_id)

    def deliver(self, actor_id: int) -> None:
        self.state.deliver(self, actor_id)

    def cancel(self, actor_id: int, note: str) -> None:
        self.state.cancel(self, actor_id, note)

    # Operations the states use.

    def move_to(self, status: OrderStatus, actor_id: int | None, note: str) -> None:
        self.order.change_status(status, actor_id, note)
        # Tell every observer. This is where the State and Observer patterns meet.
        self.publisher.publish(
            OrderEvent(
                type=EVENT_FOR_STATUS[status],
                order_id=self.order.id,
                customer_id=self.order.user_id,
                total=self.order.total_amount,
                actor_id=actor_id,
                refunded=self._refunded,
            ),
            self.session,
        )

    def restore_stock(self) -> None:
        books = BookRepository(self.session).lock_many([item.book_id for item in self.order.items])
        for item in self.order.items:
            books[item.book_id].stock += item.quantity

    def refund_payment(self) -> None:
        """Simulate refunding the successful payment, recorded as a new payment row."""
        # A locking read, so a payment committed moments ago is always seen.
        paid = self.session.scalar(
            select(Payment)
            .where(Payment.order_id == self.order.id, Payment.status == PaymentStatus.SUCCESS)
            .with_for_update()
        )
        self.session.add(
            Payment(
                order_id=self.order.id,
                method=paid.method,
                amount=paid.amount,
                status=PaymentStatus.REFUNDED,
                transaction_ref=f"REFUND-{uuid.uuid4().hex[:12].upper()}",
            )
        )
        self._refunded = True
