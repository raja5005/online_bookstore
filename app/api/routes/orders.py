"""Order endpoints, for customers only. Each customer sees only their own orders."""
from fastapi import APIRouter, status

from app.api.deps import CurrentCustomer, DbSession, PageNumber, PageSize
from app.models import Order
from app.schemas.order import OrderCreate, OrderOut, OrderPage
from app.schemas.payment import PaymentAttemptOut, PaymentDetails
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def place_order(data: OrderCreate, session: DbSession, customer: CurrentCustomer) -> Order:
    """Place an order for everything in the cart. Stock is reserved and the cart is emptied."""
    return OrderService(session).place_order(customer.id, data.shipping_address)


@router.get("", response_model=OrderPage)
def list_orders(
    session: DbSession, customer: CurrentCustomer, page: PageNumber = 1, page_size: PageSize = 20
) -> dict:
    """List your orders, newest first."""
    return OrderService(session).list_orders(customer.id, page, page_size)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, session: DbSession, customer: CurrentCustomer) -> Order:
    """Show an order with its books, payment attempts and status history."""
    return OrderService(session).get_order(customer.id, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, session: DbSession, customer: CurrentCustomer) -> Order:
    """Cancel an order that has not shipped yet. Stock is restored and any payment is refunded."""
    return OrderService(session).cancel_as_customer(customer.id, order_id)


@router.post(
    "/{order_id}/payments", response_model=PaymentAttemptOut, status_code=status.HTTP_201_CREATED
)
def pay_for_order(
    order_id: int, details: PaymentDetails, session: DbSession, customer: CurrentCustomer
) -> dict:
    """Pay for a pending order. All methods are simulated.

    The attempt is recorded either way. Check `payment.status` in the response:
    SUCCESS marks the order PAID, and FAILED leaves it PENDING so you can retry.
    """
    payment, order = PaymentService(session).pay(customer.id, order_id, details)
    return {"payment": payment, "order": order}
