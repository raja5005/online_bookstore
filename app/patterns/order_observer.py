"""Observer pattern: notifications when an order changes.

OrderEventPublisher is the subject. Code that changes an order publishes an
OrderEvent and does not need to know who is listening. Each observer that has
subscribed receives the event through update() and reacts in its own way:

    InAppNotifier   saves a notification the customer sees on the website
    EmailNotifier   sends an email (simulated: written to the server log)

Adding another reaction, such as a text message, means writing one observer and
subscribing it in build_default_publisher(). The order code does not change.

Timing: the in-app notification is saved in the same database transaction as
the order change, so either both are saved or neither is. Emails are held back
until that transaction commits, so a change that is rolled back never sends one.
"""
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import Notification, NotificationType, User

# --- The event ------------------------------------------------------------


@dataclass(frozen=True)
class OrderEvent:
    type: NotificationType
    order_id: int
    customer_id: int
    total: Decimal
    actor_id: int | None = None
    refunded: bool = False


def describe(order_event: OrderEvent) -> tuple[str, str]:
    """The subject line and message the customer receives for an event."""
    number = f"#{order_event.order_id}"
    total = f"${order_event.total:,.2f}"
    match order_event.type:
        case NotificationType.ORDER_PLACED:
            return (
                f"Order {number} received",
                f"We received order {number} for {total}. Please complete payment to confirm it.",
            )
        case NotificationType.ORDER_PAID:
            return (
                f"Payment received for order {number}",
                f"Thank you! We received your payment of {total} for order {number}. "
                "We'll let you know when it ships.",
            )
        case NotificationType.ORDER_SHIPPED:
            return f"Order {number} has shipped", f"Good news: order {number} is on its way."
        case NotificationType.ORDER_DELIVERED:
            return (
                f"Order {number} was delivered",
                f"Order {number} has been delivered. Enjoy your books!",
            )
        case NotificationType.ORDER_CANCELLED:
            by_customer = order_event.actor_id == order_event.customer_id
            who = "You cancelled" if by_customer else "We cancelled"
            refund = f" Your payment of {total} has been refunded." if order_event.refunded else ""
            return f"Order {number} was cancelled", f"{who} order {number}.{refund}"
    raise ValueError(f"No message for {order_event.type}")


# --- Subject and observer interface ---------------------------------------


class OrderObserver(ABC):
    @abstractmethod
    def update(self, order_event: OrderEvent, session: Session) -> None:
        """React to an order event."""


class OrderEventPublisher:
    """The Observer pattern's subject. It keeps a list of observers and tells each one."""

    def __init__(self) -> None:
        self._observers: list[OrderObserver] = []

    def subscribe(self, observer: OrderObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: OrderObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    @property
    def observers(self) -> tuple[OrderObserver, ...]:
        return tuple(self._observers)

    def publish(self, order_event: OrderEvent, session: Session) -> None:
        for observer in self._observers:
            observer.update(order_event, session)


# --- Concrete observers ---------------------------------------------------


class InAppNotifier(OrderObserver):
    """Saves a notification for the customer, in the same transaction as the change."""

    def update(self, order_event: OrderEvent, session: Session) -> None:
        _, message = describe(order_event)
        session.add(
            Notification(
                user_id=order_event.customer_id,
                order_id=order_event.order_id,
                type=order_event.type,
                message=message,
            )
        )


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


email_log = logging.getLogger("bookstore.email")
if not email_log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("EMAIL:    %(message)s"))
    email_log.addHandler(_handler)
    email_log.setLevel(logging.INFO)
    email_log.propagate = False


def log_email(email: Email) -> None:
    """Simulated sending: no real email leaves the computer."""
    email_log.info("to=%s | %s | %s", email.to, email.subject, email.body)


_OUTBOX = "order_emails_waiting_for_commit"


class EmailNotifier(OrderObserver):
    """Emails the customer, but only once the change has been committed."""

    def __init__(self, send: Callable[[Email], None] = log_email) -> None:
        self.send = send

    def update(self, order_event: OrderEvent, session: Session) -> None:
        customer = session.get(User, order_event.customer_id)
        subject, body = describe(order_event)
        session.info.setdefault(_OUTBOX, []).append((self, Email(customer.email, subject, body)))


@event.listens_for(Session, "after_commit")
def _send_waiting_emails(session: Session) -> None:
    for notifier, email in session.info.pop(_OUTBOX, []):
        try:
            notifier.send(email)
        except Exception:
            # The order change is already saved. A failed email must not undo it.
            email_log.exception("Could not send email to %s", email.to)


@event.listens_for(Session, "after_rollback")
def _discard_waiting_emails(session: Session) -> None:
    session.info.pop(_OUTBOX, None)


# --- The application's publisher ------------------------------------------


def build_default_publisher() -> OrderEventPublisher:
    publisher = OrderEventPublisher()
    publisher.subscribe(InAppNotifier())
    publisher.subscribe(EmailNotifier())
    return publisher


order_events = build_default_publisher()
