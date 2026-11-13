"""Cancelling, shipping and delivering orders through the API."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, BrokenBarrierError

import pytest
from sqlalchemy import select, text

from app.core.database import DatabaseManager
from app.core.exceptions import InvalidOrderTransition
from app.models import User, UserRole
from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService
from tests.conftest import ADMIN_EMAIL, CUSTOMER_EMAIL, add_user, login

pytestmark = pytest.mark.usefixtures("catalog")

CLEAN_CODE = 1
CARD = {
    "method": "CREDIT_CARD",
    "cardholder_name": "Pat Doe",
    "card_number": "4242424242424242",
    "expiry_month": 12,
    "expiry_year": date.today().year + 2,
    "cvv": "123",
}


@pytest.fixture
def headers(client, customer_headers, admin_headers):
    return {"customer": customer_headers, "admin": admin_headers}


def place_order(client, customer, quantity=2) -> int:
    client.post("/api/cart/items", json={"book_id": CLEAN_CODE, "quantity": quantity}, headers=customer)
    response = client.post("/api/orders", json={"shipping_address": "1 Main Street"}, headers=customer)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def paid_order(client, customer) -> int:
    order_id = place_order(client, customer)
    response = client.post(f"/api/orders/{order_id}/payments", json=CARD, headers=customer)
    assert response.json()["order"]["status"] == "PAID"
    return order_id


def shipped_order(client, headers) -> int:
    order_id = paid_order(client, headers["customer"])
    assert admin(client, headers, order_id, "ship").status_code == 200
    return order_id


def admin(client, headers, order_id, action):
    return client.post(f"/api/admin/orders/{order_id}/{action}", headers=headers["admin"])


def cancel(client, customer, order_id):
    return client.post(f"/api/orders/{order_id}/cancel", headers=customer)


def stock() -> int:
    with DatabaseManager().engine.connect() as connection:
        return connection.execute(text("SELECT stock FROM books WHERE id = :i"), {"i": CLEAN_CODE}).scalar()


def user_id(email: str) -> int:
    with DatabaseManager().new_session() as session:
        return session.scalar(select(User.id).where(User.email == email))


def transitions(order: dict) -> list[tuple]:
    return [(h["from_status"], h["to_status"]) for h in order["history"]]


# --- Customer cancelling --------------------------------------------------


def test_customer_cancels_unpaid_order(client, headers):
    order_id = place_order(client, headers["customer"])
    assert stock() == 23
    response = cancel(client, headers["customer"], order_id)
    assert response.status_code == 200
    order = response.json()
    assert order["status"] == "CANCELLED"
    assert order["available_actions"] == []
    assert order["history"][-1]["note"] == "Cancelled by customer"
    assert order["payments"] == []
    assert stock() == 25


def test_customer_cancels_paid_order_and_is_refunded(client, headers):
    order_id = paid_order(client, headers["customer"])
    order = cancel(client, headers["customer"], order_id).json()
    assert order["status"] == "CANCELLED"
    assert order["history"][-1]["note"] == "Cancelled by customer, payment refunded"
    payments = [(p["method"], p["status"], p["amount"]) for p in order["payments"]]
    assert payments == [("CREDIT_CARD", "SUCCESS", "89.98"), ("CREDIT_CARD", "REFUNDED", "89.98")]
    assert order["payments"][-1]["transaction_ref"].startswith("REFUND-")
    assert stock() == 25


def test_shipped_order_cannot_be_cancelled(client, headers):
    order_id = shipped_order(client, headers)
    response = cancel(client, headers["customer"], order_id)
    assert response.status_code == 409
    assert response.json()["detail"] == "A shipped order cannot be cancelled."
    assert stock() == 23


def test_cancelling_twice_restores_stock_once(client, headers):
    order_id = place_order(client, headers["customer"])
    cancel(client, headers["customer"], order_id)
    response = cancel(client, headers["customer"], order_id)
    assert response.status_code == 409
    assert "already been cancelled" in response.json()["detail"]
    assert stock() == 25


def test_customer_cannot_cancel_another_customers_order(client, headers):
    order_id = place_order(client, headers["customer"])
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    assert cancel(client, other, order_id).status_code == 404
    assert stock() == 23


@pytest.mark.parametrize("card_number", ["4242424242424242", "4000000000000002"])
def test_cancelled_order_cannot_be_paid(client, headers, card_number):
    order_id = place_order(client, headers["customer"])
    cancel(client, headers["customer"], order_id)
    details = {**CARD, "card_number": card_number}
    response = client.post(f"/api/orders/{order_id}/payments", json=details, headers=headers["customer"])
    assert response.status_code == 409
    assert client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()["payments"] == []


@pytest.mark.parametrize(
    ("make_order", "expected"),
    [
        (lambda c, h: place_order(c, h["customer"]), ["pay", "cancel"]),
        (lambda c, h: paid_order(c, h["customer"]), ["ship", "cancel"]),
        (shipped_order, ["deliver"]),
    ],
)
def test_orders_report_what_can_be_done_next(client, headers, make_order, expected):
    order_id = make_order(client, headers)
    detail = client.get(f"/api/orders/{order_id}", headers=headers["customer"]).json()
    summary = client.get("/api/orders", headers=headers["customer"]).json()["items"][0]
    assert detail["available_actions"] == expected
    assert summary["available_actions"] == expected


# --- Admin shipping and delivering ----------------------------------------


def test_full_lifecycle(client, headers):
    order_id = shipped_order(client, headers)
    response = admin(client, headers, order_id, "deliver")
    assert response.status_code == 200
    order = response.json()
    assert order["status"] == "DELIVERED"
    assert order["available_actions"] == []
    assert transitions(order) == [
        (None, "PENDING"),
        ("PENDING", "PAID"),
        ("PAID", "SHIPPED"),
        ("SHIPPED", "DELIVERED"),
    ]


def test_history_records_which_admin_shipped(client, headers):
    order_id = shipped_order(client, headers)
    with DatabaseManager().engine.connect() as connection:
        changed_by = connection.execute(
            text("SELECT changed_by FROM order_status_history WHERE order_id = :o AND to_status = 'SHIPPED'"),
            {"o": order_id},
        ).scalar()
    assert changed_by == user_id(ADMIN_EMAIL)


@pytest.mark.parametrize(
    ("make_order", "action", "message"),
    [
        (lambda c, h: place_order(c, h["customer"]), "ship", "A pending order cannot be shipped."),
        (lambda c, h: paid_order(c, h["customer"]), "deliver", "A paid order cannot be delivered."),
        (shipped_order, "ship", "This order has already been shipped."),
        (shipped_order, "cancel", "A shipped order cannot be cancelled."),
    ],
)
def test_admin_actions_follow_the_lifecycle(client, headers, make_order, action, message):
    order_id = make_order(client, headers)
    before = client.get(f"/api/admin/orders/{order_id}", headers=headers["admin"]).json()
    response = admin(client, headers, order_id, action)
    assert response.status_code == 409
    assert response.json()["detail"] == message
    after = client.get(f"/api/admin/orders/{order_id}", headers=headers["admin"]).json()
    assert after["status"] == before["status"]
    assert len(after["history"]) == len(before["history"])


def test_delivered_order_cannot_be_cancelled(client, headers):
    order_id = shipped_order(client, headers)
    admin(client, headers, order_id, "deliver")
    assert admin(client, headers, order_id, "cancel").status_code == 409
    assert cancel(client, headers["customer"], order_id).status_code == 409


def test_admin_cancels_paid_order(client, headers):
    order_id = paid_order(client, headers["customer"])
    order = admin(client, headers, order_id, "cancel").json()
    assert order["status"] == "CANCELLED"
    assert order["history"][-1]["note"] == "Cancelled by the store, payment refunded"
    assert order["payments"][-1]["status"] == "REFUNDED"
    assert stock() == 25


def test_unknown_order_is_not_found(client, headers):
    assert admin(client, headers, 9999, "ship").status_code == 404
    assert client.get("/api/admin/orders/9999", headers=headers["admin"]).status_code == 404


# --- Admin access ---------------------------------------------------------


@pytest.mark.parametrize("action", ["ship", "deliver", "cancel"])
def test_customers_cannot_use_admin_actions(client, headers, action):
    order_id = paid_order(client, headers["customer"])
    response = client.post(f"/api/admin/orders/{order_id}/{action}", headers=headers["customer"])
    assert response.status_code == 403


def test_customers_cannot_list_all_orders(client, headers):
    assert client.get("/api/admin/orders", headers=headers["customer"]).status_code == 403
    assert client.get("/api/admin/orders").status_code == 401


def test_admins_use_their_own_cancel_route(client, headers):
    order_id = place_order(client, headers["customer"])
    assert cancel(client, headers["admin"], order_id).status_code == 403


# --- Admin order list -----------------------------------------------------


def test_admin_sees_every_customers_orders(client, headers):
    first = place_order(client, headers["customer"], quantity=1)
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    second = place_order(client, other, quantity=1)

    body = client.get("/api/admin/orders", headers=headers["admin"]).json()
    assert [o["id"] for o in body["items"]] == [second, first]
    assert [o["customer"]["email"] for o in body["items"]] == ["other@example.com", CUSTOMER_EMAIL]


def test_admin_filters_orders_by_status(client, headers):
    pending = place_order(client, headers["customer"], quantity=1)
    paid = paid_order(client, headers["customer"])
    body = client.get("/api/admin/orders", params={"status": "PAID"}, headers=headers["admin"]).json()
    assert [o["id"] for o in body["items"]] == [paid]
    body = client.get("/api/admin/orders", params={"status": "PENDING"}, headers=headers["admin"]).json()
    assert [o["id"] for o in body["items"]] == [pending]


def test_invalid_status_filter_is_rejected(client, headers):
    assert client.get("/api/admin/orders", params={"status": "LOST"}, headers=headers["admin"]).status_code == 422


def test_admin_order_detail_includes_the_customer(client, headers):
    order_id = place_order(client, headers["customer"])
    order = client.get(f"/api/admin/orders/{order_id}", headers=headers["admin"]).json()
    assert order["customer"]["email"] == CUSTOMER_EMAIL
    assert order["shipping_address"] == "1 Main Street"


# --- Simultaneous changes -------------------------------------------------


def hold_after_reading(monkeypatch, *method_names):
    """Make each request pause right after reading the order, until both have.

    Without row locks both requests would read the same status and both would
    act on it. With the lock, the second cannot read until the first commits,
    so the pause times out and they run one after the other.
    """
    both_have_read = Barrier(2)

    for name in method_names:
        original = getattr(OrderRepository, name)

        def read_then_wait(self, *args, _original=original):
            order = _original(self, *args)
            try:
                both_have_read.wait(timeout=1)
            except BrokenBarrierError:
                pass
            return order

        monkeypatch.setattr(OrderRepository, name, read_then_wait)


def run_together(*tasks):
    def run(task):
        try:
            task()
            return "ok"
        except InvalidOrderTransition:
            return "refused"

    with ThreadPoolExecutor(len(tasks)) as pool:
        return list(pool.map(run, tasks))


def as_session(work):
    def task():
        with DatabaseManager().new_session() as session:
            work(OrderService(session))

    return task


def test_simultaneous_cancels_restore_stock_once(client, headers, monkeypatch):
    order_id = place_order(client, headers["customer"])
    customer = user_id(CUSTOMER_EMAIL)
    hold_after_reading(monkeypatch, "lock_for_customer")

    results = run_together(
        as_session(lambda service: service.cancel_as_customer(customer, order_id)),
        as_session(lambda service: service.cancel_as_customer(customer, order_id)),
    )
    assert sorted(results) == ["ok", "refused"]
    assert stock() == 25


def test_cancel_and_ship_at_the_same_moment(client, headers, monkeypatch):
    order_id = paid_order(client, headers["customer"])
    customer, admin_id = user_id(CUSTOMER_EMAIL), user_id(ADMIN_EMAIL)
    hold_after_reading(monkeypatch, "lock_for_customer", "lock")

    results = run_together(
        as_session(lambda service: service.cancel_as_customer(customer, order_id)),
        as_session(lambda service: service.ship(admin_id, order_id)),
    )
    assert sorted(results) == ["ok", "refused"]

    order = client.get(f"/api/admin/orders/{order_id}", headers=headers["admin"]).json()
    if order["status"] == "CANCELLED":
        assert stock() == 25
        assert order["payments"][-1]["status"] == "REFUNDED"
    else:
        assert order["status"] == "SHIPPED"
        assert stock() == 23
        assert [p["status"] for p in order["payments"]] == ["SUCCESS"]
