"""Paying for an order, using the payment strategy the customer chose."""
from sqlalchemy.orm import Session

from app.core.exceptions import OrderNotFound, OrderNotPayable
from app.models import Order, Payment, PaymentMethod, PaymentStatus
from app.patterns.order_state import OrderLifecycle
from app.patterns.payment_strategy import PaymentProcessor
from app.repositories.order_repository import OrderRepository

METHOD_NAMES = {
    PaymentMethod.CREDIT_CARD: "credit card",
    PaymentMethod.PAYPAL: "PayPal",
    PaymentMethod.BANK_TRANSFER: "bank transfer",
}


class PaymentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.orders = OrderRepository(session)

    def pay(self, user_id: int, order_id: int, details) -> tuple[Payment, Order]:
        # The lock means a double-clicked Pay button cannot charge twice: the
        # second request waits, then sees the order is already paid.
        order = self.orders.lock_for_customer(order_id, user_id)
        if order is None:
            raise OrderNotFound()
        lifecycle = OrderLifecycle(order, self.session)
        # Ask the order's state before charging, so no money moves for an
        # order that could not become PAID.
        if "pay" not in lifecycle.actions:
            raise OrderNotPayable()

        method = PaymentMethod(details.method)
        result = PaymentProcessor.for_method(method).charge(order.total_amount, details)

        # Every attempt is recorded. A failure leaves the order PENDING so the
        # customer can try again, possibly with a different method.
        payment = Payment(
            order_id=order.id,
            method=method,
            amount=order.total_amount,
            status=PaymentStatus.SUCCESS if result.succeeded else PaymentStatus.FAILED,
            transaction_ref=result.transaction_ref,
            failure_reason=result.failure_reason,
        )
        self.session.add(payment)
        if result.succeeded:
            lifecycle.pay(f"Paid by {METHOD_NAMES[method]}")
        self.session.commit()

        self.session.expire_all()
        return payment, self.orders.get_for_customer(order_id, user_id)
