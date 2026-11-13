"""Book administration: adding, editing and withdrawing books."""
import pytest
from sqlalchemy import text

from app.core.database import DatabaseManager

pytestmark = pytest.mark.usefixtures("catalog")

BOOKS = "/api/admin/books"
NEW_BOOK = {
    "isbn": "9781234567897",
    "title": "A New Book",
    "description": "About something.",
    "price": "19.50",
    "stock": 7,
    "category_id": 1,
    "authors": ["New Writer", "Jane Austen"],
}


def count(table: str) -> int:
    with DatabaseManager().engine.connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


# --- Access ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"), [("get", BOOKS), ("post", BOOKS), ("patch", f"{BOOKS}/1")]
)
def test_requires_login(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_customers_cannot_add_books(client, customer_headers):
    assert client.post(BOOKS, json=NEW_BOOK, headers=customer_headers).status_code == 403
    assert count("books") == 14


def test_customers_cannot_edit_books(client, customer_headers):
    response = client.patch(f"{BOOKS}/1", json={"price": "0.01"}, headers=customer_headers)
    assert response.status_code == 403
    assert client.get("/api/books/1").json()["price"] == "44.99"


def test_customers_cannot_list_withdrawn_books(client, customer_headers):
    assert client.get(BOOKS, headers=customer_headers).status_code == 403


# --- Adding ---------------------------------------------------------------


def test_add_book(client, admin_headers):
    response = client.post(BOOKS, json=NEW_BOOK, headers=admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "A New Book"
    assert body["price"] == "19.50"
    assert body["category"]["name"] == "Programming"
    assert body["authors"] == ["New Writer", "Jane Austen"]
    assert client.get(f"/api/books/{body['id']}").status_code == 200


def test_add_book_reuses_existing_authors(client, admin_headers):
    before = count("authors")
    client.post(BOOKS, json=NEW_BOOK, headers=admin_headers)
    assert count("authors") == before + 1


def test_add_book_removes_duplicate_author_names(client, admin_headers):
    payload = {**NEW_BOOK, "authors": ["Pat Doe", "PAT DOE", " Pat Doe "]}
    assert client.post(BOOKS, json=payload, headers=admin_headers).json()["authors"] == ["Pat Doe"]


def test_add_book_accepts_hyphenated_isbn(client, admin_headers):
    payload = {**NEW_BOOK, "isbn": "978-1-234-56789-7"}
    assert client.post(BOOKS, json=payload, headers=admin_headers).json()["isbn"] == "9781234567897"


def test_description_and_cover_are_optional(client, admin_headers):
    payload = {k: v for k, v in NEW_BOOK.items() if k != "description"}
    body = client.post(BOOKS, json=payload, headers=admin_headers).json()
    assert body["description"] is None
    assert body["cover_url"] is None


def test_duplicate_isbn_conflicts_and_leaves_nothing_behind(client, admin_headers):
    authors_before = count("authors")
    response = client.post(BOOKS, json={**NEW_BOOK, "isbn": "9780132350884"}, headers=admin_headers)
    assert response.status_code == 409
    assert "ISBN" in response.json()["detail"]
    assert count("books") == 14
    assert count("authors") == authors_before


def test_unknown_category_is_not_found(client, admin_headers):
    response = client.post(BOOKS, json={**NEW_BOOK, "category_id": 999}, headers=admin_headers)
    assert response.status_code == 404
    assert count("books") == 14


@pytest.mark.parametrize(
    "changes",
    [
        {"isbn": "123"},
        {"isbn": "97812345678XX"},
        {"isbn": 9781234567897},
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 256},
        {"price": "-1"},
        {"price": "0"},
        {"price": "1.999"},
        {"price": "123456789.00"},
        {"price": "free"},
        {"stock": -1},
        {"stock": 1_000_001},
        {"category_id": 0},
        {"authors": []},
        {"authors": [""]},
        {"authors": ["x" * 121]},
        {"cover_url": "javascript:alert(1)"},
        {"cover_url": "not a url"},
    ],
)
def test_add_rejects_invalid_input(client, admin_headers, changes):
    response = client.post(BOOKS, json={**NEW_BOOK, **changes}, headers=admin_headers)
    assert response.status_code == 422
    assert count("books") == 14


@pytest.mark.parametrize("field", ["isbn", "title", "price", "category_id", "authors"])
def test_add_requires_field(client, admin_headers, field):
    payload = {k: v for k, v in NEW_BOOK.items() if k != field}
    assert client.post(BOOKS, json=payload, headers=admin_headers).status_code == 422


# --- Updating -------------------------------------------------------------


def test_update_changes_only_the_fields_sent(client, admin_headers):
    response = client.patch(f"{BOOKS}/1", json={"price": "39.99", "stock": 3}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == "39.99"
    assert body["stock"] == 3
    assert body["title"] == "Clean Code"
    assert body["authors"] == ["Robert C. Martin"]


def test_update_can_replace_and_reorder_authors(client, admin_headers):
    response = client.patch(
        f"{BOOKS}/2",
        json={"authors": ["John Vlissides", "Someone New", "Erich Gamma"]},
        headers=admin_headers,
    )
    assert response.json()["authors"] == ["John Vlissides", "Someone New", "Erich Gamma"]
    assert client.get("/api/books/2").json()["authors"] == [
        "John Vlissides",
        "Someone New",
        "Erich Gamma",
    ]


def test_update_can_clear_optional_fields(client, admin_headers):
    body = client.patch(f"{BOOKS}/1", json={"description": None}, headers=admin_headers).json()
    assert body["description"] is None


@pytest.mark.parametrize("field", ["title", "price", "stock", "isbn", "category_id", "authors", "is_active"])
def test_update_rejects_null_for_required_fields(client, admin_headers, field):
    assert client.patch(f"{BOOKS}/1", json={field: None}, headers=admin_headers).status_code == 422


def test_update_with_no_fields_changes_nothing(client, admin_headers):
    response = client.patch(f"{BOOKS}/1", json={}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["price"] == "44.99"


def test_update_unknown_book_is_not_found(client, admin_headers):
    assert client.patch(f"{BOOKS}/9999", json={"stock": 1}, headers=admin_headers).status_code == 404


def test_update_to_a_taken_isbn_conflicts(client, admin_headers):
    response = client.patch(f"{BOOKS}/1", json={"isbn": "9780201633610"}, headers=admin_headers)
    assert response.status_code == 409


def test_update_keeping_the_same_isbn_is_allowed(client, admin_headers):
    response = client.patch(f"{BOOKS}/1", json={"isbn": "9780132350884"}, headers=admin_headers)
    assert response.status_code == 200


def test_update_to_unknown_category_is_not_found(client, admin_headers):
    response = client.patch(f"{BOOKS}/1", json={"category_id": 999}, headers=admin_headers)
    assert response.status_code == 404


# --- Withdrawing ----------------------------------------------------------


def test_withdrawn_book_leaves_the_shop_but_stays_in_admin(client, admin_headers):
    response = client.patch(f"{BOOKS}/1", json={"is_active": False}, headers=admin_headers)
    assert response.json()["is_active"] is False
    assert client.get("/api/books/1").status_code == 404
    assert client.get("/api/books").json()["total"] == 13
    assert client.get(BOOKS, headers=admin_headers).json()["total"] == 14


def test_withdrawn_book_can_be_restored(client, admin_headers):
    client.patch(f"{BOOKS}/1", json={"is_active": False}, headers=admin_headers)
    client.patch(f"{BOOKS}/1", json={"is_active": True}, headers=admin_headers)
    assert client.get("/api/books/1").status_code == 200


def test_admin_list_supports_search(client, admin_headers):
    body = client.get(BOOKS, params={"search": "Dune"}, headers=admin_headers).json()
    assert [b["id"] for b in body["items"]] == [12]
