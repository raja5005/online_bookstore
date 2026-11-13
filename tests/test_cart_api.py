"""Shopping cart: adding, changing and removing books, with stock limits."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, text

from app.core.database import DatabaseManager
from app.models import User, UserRole
from app.services.cart_service import CartService
from tests.conftest import CUSTOMER_EMAIL, add_user, login

pytestmark = pytest.mark.usefixtures("catalog")

CART = "/api/cart"
ITEMS = "/api/cart/items"
CLEAN_CODE, DESIGN_PATTERNS, OUT_OF_STOCK, PRIDE = 1, 2, 5, 8


def set_book(book_id: int, **columns) -> None:
    assignments = ", ".join(f"{name} = :{name}" for name in columns)
    with DatabaseManager().engine.begin() as connection:
        connection.execute(text(f"UPDATE books SET {assignments} WHERE id = :id"), {**columns, "id": book_id})


def add(client, headers, book_id, quantity=1):
    return client.post(ITEMS, json={"book_id": book_id, "quantity": quantity}, headers=headers)


def quantities(body: dict) -> dict[int, int]:
    return {item["book"]["id"]: item["quantity"] for item in body["items"]}


# --- Access ---------------------------------------------------------------


def test_cart_requires_login(client):
    assert client.get(CART).status_code == 401
    assert client.post(ITEMS, json={"book_id": 1}).status_code == 401


def test_admins_do_not_have_carts(client, admin_headers):
    assert client.get(CART, headers=admin_headers).status_code == 403
    assert add(client, admin_headers, CLEAN_CODE).status_code == 403


def test_customers_only_see_their_own_cart(client, customer_headers):
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other_headers = login(client, "other@example.com", "other-password")
    add(client, customer_headers, CLEAN_CODE)
    assert client.get(CART, headers=other_headers).json()["items"] == []


# --- Viewing --------------------------------------------------------------


def test_new_cart_is_empty(client, customer_headers):
    assert client.get(CART, headers=customer_headers).json() == {
        "items": [],
        "item_count": 0,
        "total": "0.00",
        "can_checkout": False,
    }


def test_cart_shows_exact_line_totals_and_grand_total(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    body = add(client, customer_headers, PRIDE, 3).json()
    lines = {item["book"]["id"]: item["line_total"] for item in body["items"]}
    assert lines == {CLEAN_CODE: "89.98", PRIDE: "29.97"}
    assert body["total"] == "119.95"
    assert body["item_count"] == 5
    assert body["can_checkout"] is True


def test_cart_shows_book_details(client, customer_headers):
    item = add(client, customer_headers, DESIGN_PATTERNS).json()["items"][0]
    assert item["book"]["title"].startswith("Design Patterns")
    assert len(item["book"]["authors"]) == 4
    assert item["available"] is True


def test_cart_uses_the_current_price(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    set_book(CLEAN_CODE, price=10)
    assert client.get(CART, headers=customer_headers).json()["total"] == "20.00"


# --- Adding ---------------------------------------------------------------


def test_add_defaults_to_one_copy(client, customer_headers):
    response = client.post(ITEMS, json={"book_id": CLEAN_CODE}, headers=customer_headers)
    assert quantities(response.json()) == {CLEAN_CODE: 1}


def test_adding_the_same_book_combines_quantities(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 2)
    assert quantities(add(client, customer_headers, CLEAN_CODE, 3).json()) == {CLEAN_CODE: 5}


def test_can_add_exactly_the_available_stock(client, customer_headers):
    assert add(client, customer_headers, CLEAN_CODE, 25).status_code == 200


def test_cannot_add_more_than_stock(client, customer_headers):
    response = add(client, customer_headers, CLEAN_CODE, 26)
    assert response.status_code == 409
    assert "Only 25" in response.json()["detail"]
    assert client.get(CART, headers=customer_headers).json()["items"] == []


def test_combined_quantity_cannot_exceed_stock(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 20)
    assert add(client, customer_headers, CLEAN_CODE, 6).status_code == 409
    assert quantities(client.get(CART, headers=customer_headers).json()) == {CLEAN_CODE: 20}


def test_cannot_add_out_of_stock_book(client, customer_headers):
    assert add(client, customer_headers, OUT_OF_STOCK).status_code == 409


def test_cannot_add_unknown_book(client, customer_headers):
    assert add(client, customer_headers, 9999).status_code == 404


def test_cannot_add_withdrawn_book(client, customer_headers):
    set_book(CLEAN_CODE, is_active=False)
    assert add(client, customer_headers, CLEAN_CODE).status_code == 404


@pytest.mark.parametrize("quantity", [0, -1, 1000, "many", 1.5, None])
def test_invalid_quantity_is_rejected(client, customer_headers, quantity):
    response = client.post(
        ITEMS, json={"book_id": CLEAN_CODE, "quantity": quantity}, headers=customer_headers
    )
    assert response.status_code == 422


def test_simultaneous_adds_are_all_counted(customer_headers):
    with DatabaseManager().new_session() as session:
        user_id = session.scalar(select(User.id).where(User.email == CUSTOMER_EMAIL))

    workers = 8
    barrier = Barrier(workers)

    def add_one(_):
        with DatabaseManager().new_session() as session:
            # A real request reads the user before it reaches the cart.
            session.get(User, user_id)
            barrier.wait()
            CartService(session).add_item(user_id, CLEAN_CODE, 1)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(add_one, range(workers)))

    with DatabaseManager().new_session() as session:
        assert CartService(session).get_cart(user_id).item_count == workers


# --- Changing quantity ----------------------------------------------------


def test_update_sets_the_quantity(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 5)
    response = client.patch(f"{ITEMS}/{CLEAN_CODE}", json={"quantity": 2}, headers=customer_headers)
    assert quantities(response.json()) == {CLEAN_CODE: 2}


def test_update_cannot_exceed_stock(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 5)
    response = client.patch(f"{ITEMS}/{CLEAN_CODE}", json={"quantity": 26}, headers=customer_headers)
    assert response.status_code == 409
    assert quantities(client.get(CART, headers=customer_headers).json()) == {CLEAN_CODE: 5}


def test_update_book_not_in_cart_is_not_found(client, customer_headers):
    response = client.patch(f"{ITEMS}/{CLEAN_CODE}", json={"quantity": 1}, headers=customer_headers)
    assert response.status_code == 404


def test_update_to_zero_is_rejected(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    response = client.patch(f"{ITEMS}/{CLEAN_CODE}", json={"quantity": 0}, headers=customer_headers)
    assert response.status_code == 422


# --- Removing -------------------------------------------------------------


def test_remove_only_deletes_that_book(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    add(client, customer_headers, PRIDE)
    response = client.delete(f"{ITEMS}/{CLEAN_CODE}", headers=customer_headers)
    assert quantities(response.json()) == {PRIDE: 1}


def test_remove_book_not_in_cart_is_not_found(client, customer_headers):
    assert client.delete(f"{ITEMS}/{CLEAN_CODE}", headers=customer_headers).status_code == 404


def test_one_customer_cannot_change_anothers_cart(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    add_user(UserRole.CUSTOMER, "other@example.com", "other-password")
    other = login(client, "other@example.com", "other-password")
    assert client.delete(f"{ITEMS}/{CLEAN_CODE}", headers=other).status_code == 404
    assert quantities(client.get(CART, headers=customer_headers).json()) == {CLEAN_CODE: 1}


# --- Changes after a book is in the cart ----------------------------------


def test_withdrawn_book_is_flagged_and_blocks_checkout(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    add(client, customer_headers, PRIDE)
    set_book(CLEAN_CODE, is_active=False)
    body = client.get(CART, headers=customer_headers).json()
    available = {item["book"]["id"]: item["available"] for item in body["items"]}
    assert available == {CLEAN_CODE: False, PRIDE: True}
    assert body["can_checkout"] is False


def test_stock_falling_below_quantity_is_flagged(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE, 5)
    set_book(CLEAN_CODE, stock=4)
    body = client.get(CART, headers=customer_headers).json()
    assert body["items"][0]["available"] is False
    assert body["can_checkout"] is False


def test_withdrawn_book_can_be_removed(client, customer_headers):
    add(client, customer_headers, CLEAN_CODE)
    set_book(CLEAN_CODE, is_active=False)
    response = client.delete(f"{ITEMS}/{CLEAN_CODE}", headers=customer_headers)
    assert response.json()["items"] == []
