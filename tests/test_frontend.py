"""The web pages are served alongside the API."""
import pytest


@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/", "Browse books"),
        ("/book.html", "/js/book.js"),
        ("/login.html", "Create account"),
        ("/cart.html", "Your cart"),
        ("/admin.html", "Manage books"),
        ("/orders.html", "Your orders"),
        ("/order.html", "Test payment details"),
        ("/admin-orders.html", "Paid, ready to ship"),
        ("/admin-order.html", "Next step"),
        ("/notifications.html", "Mark all as read"),
    ],
)
def test_pages_are_served(client, path, marker):
    response = client.get(path)
    assert response.status_code == 200
    assert marker in response.text


def test_browsers_are_told_to_check_for_updates(client):
    assert client.get("/js/api.js").headers["cache-control"] == "no-cache"
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_api_docs_are_not_hidden_by_the_frontend(client):
    assert "Swagger" in client.get("/docs").text


def test_project_files_are_not_served(client):
    for path in ("/.env", "/../.env", "/app/main.py", "/db/schema.sql"):
        assert client.get(path).status_code == 404
