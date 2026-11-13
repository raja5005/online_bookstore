"""State pattern: every action tried in every status, without a database."""
from decimal import Decimal

import pytest

from app.core.exceptions import InvalidOrderTransition
from app.models import Order, OrderStatus
from app.patterns.order_observer import OrderEventPublisher
from app.patterns.order_state import EVENT_FOR_STATUS, STATES, OrderLifecycle, state_for

S = OrderStatus

# The complete list of allowed changes. Every other combination must be refused.
ALLOWED = {
    (S.PENDING, "pay"): (S.PAID, []),
    (S.PENDING, "cancel"): (S.CANCELLED, ["restore_stock"]),
    (S.PAID, "ship"): (S.SHIPPED, []),
    (S.PAID, "cancel"): (S.CANCELLED, ["restore_stock", "refund_payment"]),
    (S.SHIPPED, "deliver"): (S.DELIVERED, []),
}

ACTIONS = {
    "pay": lambda lifecycle: lifecycle.pay("Paid by test"),
    "ship": lambda lifecycle: lifecycle.ship(actor_id=7),
    "deliver": lambda lifecycle: lifecycle.deliver(actor_id=7),
    "cancel": lambda lifecycle: lifecycle.cancel(actor_id=7, note="Cancelled by test"),
}


class RecordingPublisher(OrderEventPublisher):
    def __init__(self) -> None:
        super().__init__()
        self.events = []

    def publish(self, order_event, session) -> None:
        self.events.append(order_event)


class RecordingLifecycle(OrderLifecycle):
    """Records stock, refund and event activity instead of touching a database."""

    def __init__(self, status: OrderStatus) -> None:
        order = Order(
            id=12, user_id=3, status=status, total_amount=Decimal("10.00"), shipping_address="1 Main Street"
        )
        super().__init__(order, session=None, publisher=RecordingPublisher())
        self.operations = []

    def restore_stock(self) -> None:
        self.operations.append("restore_stock")

    def refund_payment(self) -> None:
        self.operations.append("refund_payment")


EVERY_COMBINATION = [(status, action) for status in OrderStatus for action in ACTIONS]


@pytest.mark.parametrize(("status", "action"), EVERY_COMBINATION)
def test_every_action_in_every_status(status, action):
    lifecycle = RecordingLifecycle(status)

    if (status, action) in ALLOWED:
        new_status, operations = ALLOWED[(status, action)]
        ACTIONS[action](lifecycle)
        assert lifecycle.order.status is new_status
        assert lifecycle.operations == operations
        change = lifecycle.order.history[-1]
        assert (change.from_status, change.to_status) == (status, new_status)
        [published] = lifecycle.publisher.events
        assert published.type is EVENT_FOR_STATUS[new_status]
        assert (published.order_id, published.customer_id) == (12, 3)
    else:
        with pytest.raises(InvalidOrderTransition):
            ACTIONS[action](lifecycle)
        assert lifecycle.order.status is status
        assert lifecycle.operations == []
        assert lifecycle.order.history == []
        assert lifecycle.publisher.events == []


def test_cancelling_a_paid_order_announces_the_refund():
    class RefundingLifecycle(RecordingLifecycle):
        def refund_payment(self) -> None:
            super().refund_payment()
            self._refunded = True

    paid = RefundingLifecycle(S.PAID)
    paid.cancel(actor_id=3, note="Cancelled by customer")
    pending = RecordingLifecycle(S.PENDING)
    pending.cancel(actor_id=3, note="Cancelled by customer")
    assert paid.publisher.events[0].refunded is True
    assert pending.publisher.events[0].refunded is False


@pytest.mark.parametrize("status", list(OrderStatus))
def test_each_state_lists_exactly_its_allowed_actions(status):
    expected = {action for (from_status, action) in ALLOWED if from_status is status}
    assert set(state_for(status).actions) == expected


def test_every_status_has_a_state():
    assert set(STATES) == set(OrderStatus)


def test_final_statuses_allow_nothing():
    assert state_for(S.DELIVERED).actions == ()
    assert state_for(S.CANCELLED).actions == ()


@pytest.mark.parametrize(
    ("status", "action", "message"),
    [
        (S.SHIPPED, "cancel", "A shipped order cannot be cancelled."),
        (S.PENDING, "ship", "A pending order cannot be shipped."),
        (S.PAID, "deliver", "A paid order cannot be delivered."),
        (S.CANCELLED, "cancel", "This order has already been cancelled."),
        (S.SHIPPED, "ship", "This order has already been shipped."),
    ],
)
def test_refusals_explain_why(status, action, message):
    with pytest.raises(InvalidOrderTransition, match=message):
        ACTIONS[action](RecordingLifecycle(status))


def test_who_made_the_change_is_recorded():
    lifecycle = RecordingLifecycle(S.PAID)
    lifecycle.ship(actor_id=42)
    assert lifecycle.order.history[-1].changed_by == 42


def test_payment_is_recorded_as_automatic():
    lifecycle = RecordingLifecycle(S.PENDING)
    lifecycle.pay("Paid by card")
    assert lifecycle.order.history[-1].changed_by is None
    assert lifecycle.order.history[-1].note == "Paid by card"
