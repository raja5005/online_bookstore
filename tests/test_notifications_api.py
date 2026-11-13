"""Notifications created by order events, and the notification endpoints."""
from datetime import date

import pytest
from sqlalchemy import text

from app.core.database import DatabaseManager
from app.models import UserRole
from app.patterns.order_observer import EmailNotifier, order_events
from tests.conftest import CUSTOMER_EMAIL, add_user, login

pytestmark = pytest.mark.usefixtures("catalog")

NOTIFICATIONS = "/api/notifications"
CARD = {
    "method": "CREDIT_CARD",
    "cardholder_name": "Pat Doe",
    "card_number": "4242424242424242",
    "expiry_month": 12,
    "expiry_year": date.today().year + 2,
    "cvv": "123",
}


@pytest.fixture
def sent_emails(monkeypatch) -> list:
    """Capture the simulated emails instead of writing them to the log."""
    sent = []
    for observer in order_events.observers:
        if isinstance(observer, EmailNotifier):
            monkeypatch.setattr(observer, "send", sent.append)
    return sent


@pytest.fixture
def headers(client, customer_headers, admin_headers):
    return {"customer": customer_headers, "admin": admin_headers}


def place_order(client, customer, quantity=2) -> int:
    client.post("/api/cart/items", json={"book_id": 1, "quantity": quantity}, headers=customer)
    response = client.post("/api/orders", json={"shipping_address": "1 Main Street"}, headers=customer)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def pay(client, customer, order_id, card_number="4242424242424242"):
    return client.post(
        f"/api/orders/{order_id}/payments", json={**CARD, "card_number": card_number}, headers=customer
    )


def messages(client, headers) -> list[tuple[str, str]]:
    body = client.get(NOTIFICATIONS, headers=headers).json()
    return [(n["type"], n["message"]) for n in body["items"]]


def count(table: str) -> int:
    with DatabaseManager().engine.connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


# --- Notifications follow the order ---------------------------------------


def test_placing_an_order_notifies_the_customer(client, headers, sent_emails):
    order_id = place_order(client, headers["customer"])
    body = client.get(NOTIFICATIONS, headers=headers["customer"]).json()
    assert body["unread"] == 1
    [notification] = body["items"]
    assert notification["type"] == "ORDER_PLACED"
    assert notification["order_id"] == order_id
    assert f"order #{order_id} for $89.98" in notification["message"]
    assert [(e.to, e.subject) for e in sent_emails] == [(CUSTOMER_EMAIL, f"Order #{order_id} received")]


def test_whole_lifecycle_sends_one_notification_and_email_per_step(client, headers, sent_emails):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id)
    client.post(f"/api/admin/orders/{order_id}/ship", headers=headers["admin"])
    client.post(f"/api/admin/orders/{order_id}/deliver", headers=headers["admin"])

    types = [kind for kind, _ in messages(client, headers["customer"])]
    assert types == ["ORDER_DELIVERED", "ORDER_SHIPPED", "ORDER_PAID", "ORDER_PLACED"]
    assert [e.subject for e in sent_emails] == [
        f"Order #{order_id} received",
        f"Payment received for order #{order_id}",
        f"Order #{order_id} has shipped",
        f"Order #{order_id} was delivered",
    ]
    assert {e.to for e in sent_emails} == {CUSTOMER_EMAIL}


def test_admins_actions_notify_the_customer_not_the_admin(client, headers):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id)
    client.post(f"/api/admin/orders/{order_id}/ship", headers=headers["admin"])
    assert client.get(NOTIFICATIONS, headers=headers["admin"]).json()["items"] == []
    assert messages(client, headers["customer"])[0][0] == "ORDER_SHIPPED"


def test_customer_cancelling_a_paid_order_hears_about_the_refund(client, headers):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id)
    client.post(f"/api/orders/{order_id}/cancel", headers=headers["customer"])
    kind, message = messages(client, headers["customer"])[0]
    assert kind == "ORDER_CANCELLED"
    assert message == f"You cancelled order #{order_id}. Your payment of $89.98 has been refunded."


def test_store_cancelling_an_unpaid_order_says_so(client, headers):
    order_id = place_order(client, headers["customer"])
    client.post(f"/api/admin/orders/{order_id}/cancel", headers=headers["admin"])
    assert messages(client, headers["customer"])[0] == ("ORDER_CANCELLED", f"We cancelled order #{order_id}.")


# --- Nothing is sent when nothing changed ---------------------------------


def test_declined_payment_sends_nothing(client, headers, sent_emails):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id, card_number="4000000000000002")
    assert [kind for kind, _ in messages(client, headers["customer"])] == ["ORDER_PLACED"]
    assert len(sent_emails) == 1


def test_refused_change_sends_nothing(client, headers, sent_emails):
    order_id = place_order(client, headers["customer"])
    assert client.post(f"/api/admin/orders/{order_id}/ship", headers=headers["admin"]).status_code == 409
    assert count("notifications") == 1
    assert len(sent_emails) == 1


def test_refused_order_sends_nothing(client, headers, sent_emails):
    client.post("/api/cart/items", json={"book_id": 1, "quantity": 2}, headers=headers["customer"])
    with DatabaseManager().engine.begin() as connection:
        connection.execute(text("UPDATE books SET stock = 1 WHERE id = 1"))
    response = client.post("/api/orders", json={"shipping_address": "1 Main Street"}, headers=headers["customer"])
    assert response.status_code == 409
    assert count("notifications") == 0
    assert sent_emails == []


# --- Reading and marking --------------------------------------------------


def test_notifications_require_login(client):
    assert client.get(NOTIFICATIONS).status_code == 401
    assert client.post(f"{NOTIFICATIONS}/read-all").status_code == 401


def test_customers_only_see_their_own(client, headers):
    place_order(client, headers["customer"])
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    assert client.get(NOTIFICATIONS, headers=other).json() == {
        "items": [],
        "total": 0,
        "unread": 0,
        "page": 1,
        "page_size": 20,
        "pages": 0,
    }


def test_mark_one_as_read(client, headers):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id)
    newest = client.get(NOTIFICATIONS, headers=headers["customer"]).json()["items"][0]
    response = client.post(f"{NOTIFICATIONS}/{newest['id']}/read", headers=headers["customer"])
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    body = client.get(NOTIFICATIONS, headers=headers["customer"]).json()
    assert body["unread"] == 1
    assert [n["is_read"] for n in body["items"]] == [True, False]


def test_unread_only_filter(client, headers):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id)
    newest = client.get(NOTIFICATIONS, headers=headers["customer"]).json()["items"][0]
    client.post(f"{NOTIFICATIONS}/{newest['id']}/read", headers=headers["customer"])
    body = client.get(NOTIFICATIONS, params={"unread_only": True}, headers=headers["customer"]).json()
    assert [n["type"] for n in body["items"]] == ["ORDER_PLACED"]


def test_mark_all_as_read(client, headers):
    order_id = place_order(client, headers["customer"])
    pay(client, headers["customer"], order_id)
    assert client.post(f"{NOTIFICATIONS}/read-all", headers=headers["customer"]).json() == {"marked": 2}
    assert client.get(NOTIFICATIONS, headers=headers["customer"]).json()["unread"] == 0
    assert client.post(f"{NOTIFICATIONS}/read-all", headers=headers["customer"]).json() == {"marked": 0}


def test_cannot_mark_another_users_notification(client, headers):
    place_order(client, headers["customer"])
    notification_id = client.get(NOTIFICATIONS, headers=headers["customer"]).json()["items"][0]["id"]
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    assert client.post(f"{NOTIFICATIONS}/{notification_id}/read", headers=other).status_code == 404
    assert client.post(f"{NOTIFICATIONS}/read-all", headers=other).json() == {"marked": 0}
    assert client.get(NOTIFICATIONS, headers=headers["customer"]).json()["unread"] == 1


def test_unknown_notification_is_not_found(client, headers):
    assert client.post(f"{NOTIFICATIONS}/9999/read", headers=headers["customer"]).status_code == 404


def test_notifications_page(client, headers):
    for _ in range(3):
        place_order(client, headers["customer"], quantity=1)
    body = client.get(NOTIFICATIONS, params={"page_size": 2, "page": 2}, headers=headers["customer"]).json()
    assert len(body["items"]) == 1
    assert body["pages"] == 2
    assert body["unread"] == 3
