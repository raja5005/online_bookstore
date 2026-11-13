"""Public catalog: listing, paging, search, filtering and book details."""
import pytest
from sqlalchemy import event, text

from app.core.database import DatabaseManager

pytestmark = pytest.mark.usefixtures("catalog")

BOOKS = "/api/books"


def ids(body: dict) -> set[int]:
    return {book["id"] for book in body["items"]}


def withdraw(book_id: int) -> None:
    with DatabaseManager().engine.begin() as connection:
        connection.execute(text("UPDATE books SET is_active = 0 WHERE id = :i"), {"i": book_id})


def test_list_includes_paging_details(client):
    body = client.get(BOOKS, params={"page_size": 5}).json()
    assert body["total"] == 14
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["pages"] == 3
    assert len(body["items"]) == 5


def test_pages_cover_every_book_once(client):
    seen = []
    for page in (1, 2, 3):
        seen += [b["id"] for b in client.get(BOOKS, params={"page": page, "page_size": 5}).json()["items"]]
    assert len(seen) == 14
    assert len(set(seen)) == 14


def test_list_is_sorted_by_title(client):
    titles = [b["title"] for b in client.get(BOOKS, params={"page_size": 3}).json()["items"]]
    assert titles[0] == "Clean Code"
    assert titles[1].startswith("Design Patterns")
    assert titles[2] == "Dune"


def test_page_past_the_end_is_empty(client):
    body = client.get(BOOKS, params={"page": 99}).json()
    assert body["items"] == []
    assert body["total"] == 14


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101}, {"category_id": 0}, {"search": "x" * 101}],
)
def test_invalid_list_parameters_are_rejected(client, params):
    assert client.get(BOOKS, params=params).status_code == 422


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("clean code", {1}),
        ("CLEAN", {1}),
        ("  dune  ", {12}),
        ("gamma", {2}),
        ("Orwell", {9}),
        ("Thomas", {4, 7}),
        ("9780201633610", {2}),
        ("978-0-201-63361-0", {2}),
        ("no such book", set()),
    ],
)
def test_search_by_title_author_or_isbn(client, term, expected):
    assert ids(client.get(BOOKS, params={"search": term}).json()) == expected


@pytest.mark.parametrize("term", ["%", "_", "' OR '1'='1"])
def test_search_treats_special_characters_literally(client, term):
    assert client.get(BOOKS, params={"search": term}).json()["total"] == 0


def test_search_for_only_a_hyphen_does_not_match_everything(client):
    # Only the titles containing a hyphen: Object-Oriented and Eighty-Four.
    assert ids(client.get(BOOKS, params={"search": "-"}).json()) == {2, 9}


def test_blank_search_returns_everything(client):
    assert client.get(BOOKS, params={"search": "   "}).json()["total"] == 14


def test_filter_by_category(client):
    assert ids(client.get(BOOKS, params={"category_id": 3}).json()) == {8, 9, 10}


def test_search_and_category_combine(client):
    assert ids(client.get(BOOKS, params={"search": "Harper", "category_id": 3}).json()) == {10}
    assert ids(client.get(BOOKS, params={"search": "Harper", "category_id": 1}).json()) == set()


def test_book_details(client):
    book = client.get(f"{BOOKS}/2").json()
    assert book["isbn"] == "9780201633610"
    assert book["price"] == "54.99"
    assert book["stock"] == 12
    assert book["in_stock"] is True
    assert book["category"] == {"id": 1, "name": "Programming"}
    assert book["description"]


def test_authors_keep_their_credited_order(client):
    assert client.get(f"{BOOKS}/2").json()["authors"] == [
        "Erich Gamma",
        "Richard Helm",
        "Ralph Johnson",
        "John Vlissides",
    ]


def test_out_of_stock_book_is_still_listed(client):
    assert client.get(f"{BOOKS}/5").json()["in_stock"] is False
    assert 5 in ids(client.get(BOOKS, params={"page_size": 100}).json())


def test_unknown_book_is_not_found(client):
    assert client.get(f"{BOOKS}/9999").status_code == 404


def test_withdrawn_book_is_hidden_from_customers(client):
    withdraw(1)
    assert client.get(f"{BOOKS}/1").status_code == 404
    assert 1 not in ids(client.get(BOOKS, params={"page_size": 100}).json())
    assert client.get(BOOKS).json()["total"] == 13


def test_list_query_count_does_not_grow_with_page_size(client):
    def queries_for(page_size: int) -> int:
        statements = []

        def record(_conn, _cursor, statement, *_args):
            statements.append(statement)

        engine = DatabaseManager().engine
        event.listen(engine, "before_cursor_execute", record)
        try:
            client.get(BOOKS, params={"page_size": page_size})
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements)

    assert queries_for(14) == queries_for(2)


def test_categories_are_listed_alphabetically(client):
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert names == sorted(names)
    assert len(names) == 5
