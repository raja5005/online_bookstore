"""Observer pattern: subscribing, publishing, and what each observer does."""
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.database import DatabaseManager
from app.models import NotificationType, UserRole
from app.patterns.order_observer import (
    EmailNotifier,
    InAppNotifier,
    OrderEvent,
    OrderEventPublisher,
    OrderObserver,
    describe,
    order_events,
)
from tests.conftest import CUSTOMER_EMAIL, CUSTOMER_PASSWORD, add_user

T = NotificationType


def make_event(event_type=T.ORDER_SHIPPED, **changes) -> OrderEvent:
    values = {"type": event_type, "order_id": 12, "customer_id": 3, "total": Decimal("89.98"), "actor_id": 1}
    return OrderEvent(**{**values, **changes})


class Recorder(OrderObserver):
    def __init__(self, name: str, log: list) -> None:
        self.name = name
        self.log = log

    def update(self, order_event, session) -> None:
        self.log.append((self.name, order_event.type))


# --- The subject ----------------------------------------------------------


def test_every_subscriber_is_told_in_order():
    log = []
    publisher = OrderEventPublisher()
    publisher.subscribe(Recorder("first", log))
    publisher.subscribe(Recorder("second", log))
    publisher.publish(make_event(), session=None)
    assert log == [("first", T.ORDER_SHIPPED), ("second", T.ORDER_SHIPPED)]


def test_unsubscribed_observer_is_not_told():
    log = []
    publisher = OrderEventPublisher()
    leaving = Recorder("leaving", log)
    publisher.subscribe(leaving)
    publisher.subscribe(Recorder("staying", log))
    publisher.unsubscribe(leaving)
    publisher.publish(make_event(), session=None)
    assert log == [("staying", T.ORDER_SHIPPED)]


def test_subscribing_twice_does_not_notify_twice():
    log = []
    publisher = OrderEventPublisher()
    observer = Recorder("once", log)
    publisher.subscribe(observer)
    publisher.subscribe(observer)
    publisher.publish(make_event(), session=None)
    assert len(log) == 1


def test_publishing_with_no_subscribers_is_harmless():
    OrderEventPublisher().publish(make_event(), session=None)


def test_the_application_subscribes_both_notifiers():
    kinds = {type(observer) for observer in order_events.observers}
    assert kinds == {InAppNotifier, EmailNotifier}


# --- Messages -------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "subject", "message"),
    [
        ({"type": T.ORDER_PLACED}, "Order #12 received", "We received order #12 for $89.98. Please complete payment to confirm it."),
        ({"type": T.ORDER_PAID}, "Payment received for order #12", "We received your payment of $89.98 for order #12"),
        ({"type": T.ORDER_SHIPPED}, "Order #12 has shipped", "order #12 is on its way"),
        ({"type": T.ORDER_DELIVERED}, "Order #12 was delivered", "Order #12 has been delivered"),
        ({"type": T.ORDER_CANCELLED, "actor_id": 3}, "Order #12 was cancelled", "You cancelled order #12."),
        ({"type": T.ORDER_CANCELLED, "actor_id": 1}, "Order #12 was cancelled", "We cancelled order #12."),
        (
            {"type": T.ORDER_CANCELLED, "actor_id": 3, "refunded": True},
            "Order #12 was cancelled",
            "You cancelled order #12. Your payment of $89.98 has been refunded.",
        ),
    ],
)
def test_each_event_has_a_clear_message(changes, subject, message):
    actual_subject, actual_message = describe(make_event(**changes))
    assert actual_subject == subject
    assert message in actual_message


def test_unrefunded_cancellation_does_not_mention_a_refund():
    assert "refund" not in describe(make_event(T.ORDER_CANCELLED))[1]


# --- Email timing ---------------------------------------------------------


@pytest.fixture
def customer_id() -> int:
    return add_user(UserRole.CUSTOMER, CUSTOMER_EMAIL, CUSTOMER_PASSWORD).id


def test_email_is_sent_only_after_commit(customer_id):
    sent = []
    notifier = EmailNotifier(send=sent.append)
    with DatabaseManager().new_session() as session:
        session.execute(text("SELECT 1"))
        notifier.update(make_event(customer_id=customer_id), session)
        assert sent == []
        session.commit()
    assert [(email.to, email.subject) for email in sent] == [(CUSTOMER_EMAIL, "Order #12 has shipped")]


def test_email_is_dropped_when_the_change_is_rolled_back(customer_id):
    sent = []
    notifier = EmailNotifier(send=sent.append)
    with DatabaseManager().new_session() as session:
        session.execute(text("SELECT 1"))
        notifier.update(make_event(customer_id=customer_id), session)
        session.rollback()
        session.execute(text("SELECT 1"))
        session.commit()
    assert sent == []


def test_a_failing_email_does_not_undo_the_change(customer_id):
    def broken_mail_server(email):
        raise ConnectionError("mail server down")

    notifier = EmailNotifier(send=broken_mail_server)
    with DatabaseManager().new_session() as session:
        session.execute(text("UPDATE users SET full_name = 'Changed' WHERE id = :i"), {"i": customer_id})
        notifier.update(make_event(customer_id=customer_id), session)
        session.commit()
    with DatabaseManager().engine.connect() as connection:
        name = connection.execute(text("SELECT full_name FROM users WHERE id = :i"), {"i": customer_id}).scalar()
    assert name == "Changed"
