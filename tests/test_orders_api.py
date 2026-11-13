"""Placing orders: all-or-nothing, with stock reserved and prices recorded."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

import pytest
from sqlalchemy import select, text

from app.core.database import DatabaseManager
from app.core.exceptions import EmptyCart, InsufficientStock
from app.models import User, UserRole
from app.repositories.book_repository import BookRepository
from app.services.order_service import OrderService
from tests.conftest import CUSTOMER_EMAIL, add_user, login

pytestmark = pytest.mark.usefixtures("catalog")

ORDERS = "/api/orders"
CLEAN_CODE, DESIGN_PATTERNS, PRIDE = 1, 2, 8
ADDRESS = "1 Main Street, Springfield"


def add(client, headers, book_id, quantity=1):
    response = client.post("/api/cart/items", json={"book_id": book_id, "quantity": quantity}, headers=headers)
    assert response.status_code == 200, response.text


def place(client, headers, address=ADDRESS):
    return client.post(ORDERS, json={"shipping_address": address}, headers=headers)


def stock(book_id: int) -> int:
    with DatabaseManager().engine.connect() as connection:
        return connection.execute(text("SELECT stock FROM books WHERE id = :i"), {"i": book_id}).scalar()


def set_book(book_id: int, **columns) -> None:
    assignments = ", ".join(f"{name} = :{name}" for name in columns)
    with DatabaseManager().engine.begin() as connection:
        connection.execute(text(f"UPDATE books SET {assignments} WHERE id = :id"), {**columns, "id": book_id})


def count(table: str) -> int:
    with DatabaseManager().engine.connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def user_id(email: str) -> int:
    with DatabaseManager().new_session() as session:
        return session.scalar(select(User.id).where(User.email == email))


# --- Access ---------------------------------------------------------------


def test_orders_require_login(client):
    assert place(client, {}).status_code == 401
    assert client.get(ORDERS).status_code == 401


def test_admins_cannot_place_orders(client, admin_headers):
    assert place(client, admin_headers).status_code == 403
    assert client.get(ORDERS, headers=admin_headers).status_code == 403


# --- Placing an order -----------------------------------------------------


def test_place_order(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    add(client, customer_headers, PRIDE, 3)
    response = place(client, customer_headers)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "PENDING"
    assert order["total_amount"] == "119.95"
    assert order["item_count"] == 5
    assert order["shipping_address"] == ADDRESS
    assert order["payments"] == []
    lines = {line["book"]["id"]: (line["quantity"], line["unit_price"], line["line_total"]) for line in order["items"]}
    assert lines == {CLEAN_CODE: (2, "44.99", "89.98"), PRIDE: (3, "9.99", "29.97")}


def test_placing_an_order_records_its_first_status(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    history = place(client, customer_headers).json()["history"]
    assert [(h["from_status"], h["to_status"], h["note"]) for h in history] == [
        (None, "PENDING", "Order placed")
    ]


def test_placing_an_order_reserves_stock(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    place(client, customer_headers)
    assert stock(CLEAN_CODE) == 23


def test_placing_an_order_empties_the_cart(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    place(client, customer_headers)
    assert client.get("/api/cart", headers=customer_headers).json()["items"] == []


def test_order_keeps_the_price_paid(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    order_id = place(client, customer_headers).json()["id"]
    set_book(CLEAN_CODE, price=99.00)
    order = client.get(f"{ORDERS}/{order_id}", headers=customer_headers).json()
    assert order["items"][0]["unit_price"] == "44.99"
    assert order["total_amount"] == "44.99"


def test_empty_cart_cannot_be_ordered(client, customer_headers):
    response = place(client, customer_headers)
    assert response.status_code == 409
    assert count("orders") == 0


@pytest.mark.parametrize("address", ["", "    ", "abc", "x" * 501])
def test_invalid_address_is_rejected(client, customer_headers, address):
    add(client, customer_headers, CLEAN_CODE)
    assert place(client, customer_headers, address).status_code == 422
    assert count("orders") == 0
    assert len(client.get("/api/cart", headers=customer_headers).json()["items"]) == 1


# --- Nothing changes when an order is refused -----------------------------


def assert_nothing_changed(client, headers, expected_stock):
    assert count("orders") == 0
    assert count("order_items") == 0
    assert count("order_status_history") == 0
    assert len(client.get("/api/cart", headers=headers).json()["items"]) == 2
    for book_id, expected in expected_stock.items():
        assert stock(book_id) == expected


def test_withdrawn_book_blocks_the_whole_order(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    add(client, customer_headers, PRIDE)
    set_book(PRIDE, is_active=False)
    response = place(client, customer_headers)
    assert response.status_code == 409
    assert "Pride and Prejudice" in response.json()["detail"]
    assert_nothing_changed(client, customer_headers, {CLEAN_CODE: 25, PRIDE: 40})


def test_insufficient_stock_blocks_the_whole_order(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    add(client, customer_headers, PRIDE, 5)
    set_book(PRIDE, stock=4)
    response = place(client, customer_headers)
    assert response.status_code == 409
    assert "Only 4" in response.json()["detail"]
    assert_nothing_changed(client, customer_headers, {CLEAN_CODE: 25, PRIDE: 4})


# --- Simultaneous orders --------------------------------------------------


def run_together(task, count_):
    barrier = Barrier(count_)

    def wrapped(index):
        barrier.wait()
        try:
            task(index)
            return "ok"
        except (InsufficientStock, EmptyCart) as exc:
            return type(exc).__name__

    with ThreadPoolExecutor(count_) as pool:
        return list(pool.map(wrapped, range(count_)))


def test_two_customers_cannot_both_buy_the_last_copy(client, customer_headers, monkeypatch):
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other_headers = login(client, "other@example.com", "other-password")
    add(client, customer_headers, CLEAN_CODE)
    add(client, other_headers, CLEAN_CODE)
    set_book(CLEAN_CODE, stock=1)
    buyers = [user_id(CUSTOMER_EMAIL), user_id("other@example.com")]

    # Hold each order just after it reads the stock, until both have read it.
    # Without the row lock both would see 1 copy and both would succeed. With
    # it, the second order cannot read until the first commits, so the wait
    # times out and the first order goes ahead alone.
    both_have_read = Barrier(2)
    original_lock_many = BookRepository.lock_many

    def lock_then_wait(self, book_ids):
        books = original_lock_many(self, book_ids)
        try:
            both_have_read.wait(timeout=1)
        except BrokenBarrierError:
            pass
        return books

    monkeypatch.setattr(BookRepository, "lock_many", lock_then_wait)

    def buy(index):
        with DatabaseManager().new_session() as session:
            session.get(User, buyers[index])
            OrderService(session).place_order(buyers[index], ADDRESS)

    results = run_together(buy, 2)
    assert sorted(results) == ["InsufficientStock", "ok"]
    assert stock(CLEAN_CODE) == 0
    assert count("orders") == 1


def test_double_clicking_place_order_creates_one_order(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 3)
    buyer = user_id(CUSTOMER_EMAIL)

    def buy(_):
        with DatabaseManager().new_session() as session:
            session.get(User, buyer)
            OrderService(session).place_order(buyer, ADDRESS)

    assert sorted(run_together(buy, 3)) == ["EmptyCart", "EmptyCart", "ok"]
    assert count("orders") == 1
    assert stock(CLEAN_CODE) == 22


# --- Viewing orders -------------------------------------------------------


def test_order_list_is_newest_first(client, customer_headers):
    ids = []
    for book_id in (CLEAN_CODE, PRIDE, DESIGN_PATTERNS):
        add(client, customer_headers, book_id)
        ids.append(place(client, customer_headers).json()["id"])
    body = client.get(ORDERS, headers=customer_headers).json()
    assert [order["id"] for order in body["items"]] == ids[::-1]
    assert body["total"] == 3
    assert body["items"][0]["item_count"] == 1


def test_order_list_pages(client, customer_headers):
    for _ in range(3):
        add(client, customer_headers, PRIDE)
        place(client, customer_headers)
    body = client.get(ORDERS, params={"page_size": 2, "page": 2}, headers=customer_headers).json()
    assert len(body["items"]) == 1
    assert body["pages"] == 2


def test_customers_only_see_their_own_orders(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    order_id = place(client, customer_headers).json()["id"]
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    assert client.get(ORDERS, headers=other).json()["items"] == []
    assert client.get(f"{ORDERS}/{order_id}", headers=other).status_code == 404


def test_unknown_order_is_not_found(client, customer_headers):
    assert client.get(f"{ORDERS}/9999", headers=customer_headers).status_code == 404
