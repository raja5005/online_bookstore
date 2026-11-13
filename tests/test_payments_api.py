"""Paying for orders through the API, with each payment strategy."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from sqlalchemy import select, text

from app.core.database import DatabaseManager
from app.core.exceptions import OrderNotPayable
from app.models import User, UserRole
from app.schemas.payment import CardDetails
from app.services.payment_service import PaymentService
from tests.conftest import CUSTOMER_EMAIL, add_user, login

pytestmark = pytest.mark.usefixtures("catalog")

CARD_NUMBER = "4242424242424242"
CARD = {
    "method": "CREDIT_CARD",
    "cardholder_name": "Pat Doe",
    "card_number": CARD_NUMBER,
    "expiry_month": 12,
    "expiry_year": date.today().year + 2,
    "cvv": "987",
}
PAYPAL = {"method": "PAYPAL", "paypal_email": "buyer@example.com"}
BANK = {
    "method": "BANK_TRANSFER",
    "account_name": "Pat Doe",
    "routing_number": "011000015",
    "account_number": "55512345678",
}
DECLINED = {
    "CREDIT_CARD": {**CARD, "card_number": "4000000000000002"},
    "PAYPAL": {**PAYPAL, "paypal_email": "declined@example.com"},
    "BANK_TRANSFER": {**BANK, "account_number": "55510000"},
}


@pytest.fixture
def order_id(client, customer_headers) -> int:
    client.post("/api/cart/items", json={"book_id": 1, "quantity": 2}, headers=customer_headers)
    response = client.post("/api/orders", json={"shipping_address": "1 Main Street"}, headers=customer_headers)
    return response.json()["id"]


def pay(client, headers, order_id, details):
    return client.post(f"/api/orders/{order_id}/payments", json=details, headers=headers)


def payment_rows() -> list[dict]:
    with DatabaseManager().engine.connect() as connection:
        return [dict(row._mapping) for row in connection.execute(text("SELECT * FROM payments"))]


# --- Access ---------------------------------------------------------------


def test_payment_requires_login(client, order_id):
    assert pay(client, {}, order_id, CARD).status_code == 401


def test_cannot_pay_another_customers_order(client, order_id):
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    assert pay(client, other, order_id, CARD).status_code == 404
    assert payment_rows() == []


def test_unknown_order_cannot_be_paid(client, customer_headers):
    assert pay(client, customer_headers, 9999, CARD).status_code == 404


# --- Successful payment ---------------------------------------------------


@pytest.mark.parametrize(
    ("details", "prefix", "note"),
    [(CARD, "CARD-", "Paid by credit card"), (PAYPAL, "PAYPAL-", "Paid by PayPal"), (BANK, "BANK-", "Paid by bank transfer")],
)
def test_successful_payment_marks_the_order_paid(client, customer_headers, order_id, details, prefix, note):
    response = pay(client, customer_headers, order_id, details)
    assert response.status_code == 201
    body = response.json()
    assert body["payment"]["status"] == "SUCCESS"
    assert body["payment"]["method"] == details["method"]
    assert body["payment"]["amount"] == "89.98"
    assert body["payment"]["transaction_ref"].startswith(prefix)
    assert body["order"]["status"] == "PAID"
    assert body["order"]["history"][-1] == {
        **body["order"]["history"][-1],
        "from_status": "PENDING",
        "to_status": "PAID",
        "note": note,
    }


def test_amount_always_comes_from_the_order(client, customer_headers, order_id):
    body = pay(client, customer_headers, order_id, {**CARD, "amount": "0.01"}).json()
    assert body["payment"]["amount"] == "89.98"


def test_paid_order_cannot_be_paid_again(client, customer_headers, order_id):
    pay(client, customer_headers, order_id, CARD)
    response = pay(client, customer_headers, order_id, PAYPAL)
    assert response.status_code == 409
    assert len(payment_rows()) == 1


# --- Failed payment -------------------------------------------------------


@pytest.mark.parametrize("method", list(DECLINED))
def test_declined_payment_is_recorded_and_order_stays_pending(client, customer_headers, order_id, method):
    response = pay(client, customer_headers, order_id, DECLINED[method])
    assert response.status_code == 201
    body = response.json()
    assert body["payment"]["status"] == "FAILED"
    assert body["payment"]["failure_reason"]
    assert body["payment"]["transaction_ref"] is None
    assert body["order"]["status"] == "PENDING"
    assert len(body["order"]["history"]) == 1


def test_customer_can_retry_with_another_method(client, customer_headers, order_id):
    pay(client, customer_headers, order_id, DECLINED["CREDIT_CARD"])
    body = pay(client, customer_headers, order_id, PAYPAL).json()
    assert body["order"]["status"] == "PAID"
    assert [(p["method"], p["status"]) for p in body["order"]["payments"]] == [
        ("CREDIT_CARD", "FAILED"),
        ("PAYPAL", "SUCCESS"),
    ]


def test_failed_payment_keeps_stock_reserved(client, customer_headers, order_id):
    pay(client, customer_headers, order_id, DECLINED["CREDIT_CARD"])
    assert client.get("/api/books/1").json()["stock"] == 23


# --- Payment details ------------------------------------------------------


def stored_text_and_references() -> tuple[str, list[str]]:
    """Every stored value except the random references, plus the references."""
    rows = payment_rows()
    references = [row["transaction_ref"] for row in rows if row["transaction_ref"]]
    text_values = " ".join(
        str(value) for row in rows for key, value in row.items() if key != "transaction_ref"
    )
    return text_values, references


def test_card_details_are_never_stored(client, customer_headers, order_id):
    pay(client, customer_headers, order_id, DECLINED["CREDIT_CARD"])
    pay(client, customer_headers, order_id, CARD)
    stored, references = stored_text_and_references()
    for secret in (CARD_NUMBER, "4000000000000002", "Pat Doe", CARD["cvv"]):
        assert secret not in stored
    # A reference is a fixed prefix plus random characters, with no room for card data.
    assert all(re.fullmatch(r"CARD-[0-9A-F]{12}", ref) for ref in references)


def test_bank_details_are_never_stored(client, customer_headers, order_id):
    pay(client, customer_headers, order_id, BANK)
    stored, references = stored_text_and_references()
    for secret in ("55512345678", "011000015", "Pat Doe"):
        assert secret not in stored
    assert all(re.fullmatch(r"BANK-[0-9A-F]{12}", ref) for ref in references)


@pytest.mark.parametrize(
    "details",
    [
        {**CARD, "card_number": "4242-abcd-4242-4242"},
        {**CARD, "card_number": "4242"},
        {**CARD, "expiry_month": 13},
        {**CARD, "cvv": "12"},
        {**CARD, "cardholder_name": ""},
        {key: value for key, value in CARD.items() if key != "cvv"},
        {**PAYPAL, "paypal_email": "not-an-email"},
        {**BANK, "routing_number": "12345678"},
        {**BANK, "account_number": "123"},
        {"method": "BITCOIN"},
        {},
    ],
)
def test_badly_formatted_details_are_rejected_without_a_record(client, customer_headers, order_id, details):
    assert pay(client, customer_headers, order_id, details).status_code == 422
    assert payment_rows() == []


# --- Simultaneous payments ------------------------------------------------


def test_double_clicking_pay_charges_once(order_id):
    with DatabaseManager().new_session() as session:
        buyer = session.scalar(select(User.id).where(User.email == CUSTOMER_EMAIL))
    barrier = Barrier(3)

    def attempt(_):
        with DatabaseManager().new_session() as session:
            session.get(User, buyer)
            barrier.wait()
            try:
                PaymentService(session).pay(buyer, order_id, CardDetails(**CARD))
                return "paid"
            except OrderNotPayable:
                return "refused"

    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(attempt, range(3)))

    assert sorted(results) == ["paid", "refused", "refused"]
    assert [row["status"] for row in payment_rows()] == ["SUCCESS"]
