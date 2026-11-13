# Week 4: Book and Cart Module

## 1. What was built

| Requirement | Result |
|---|---|
| FR-1 List books | `GET /api/books` returns active books a page at a time. |
| FR-2 Search | The `search` parameter matches title, author or ISBN. |
| FR-3 Filter | The `category_id` parameter limits results to one category. |
| FR-4 Book details | `GET /api/books/{id}` includes price and availability. |
| FR-9 Add to cart | `POST /api/cart/items` adds a book, or combines quantities. |
| FR-10 Change quantity | `PATCH /api/cart/items/{book_id}` sets the quantity. |
| FR-11 Remove | `DELETE /api/cart/items/{book_id}` removes the book. |
| FR-12 View cart | `GET /api/cart` shows line totals and a grand total. |
| FR-13 Stock limit | Quantities above the available stock return HTTP 409. |
| FR-23 Add book | `POST /api/admin/books` (admin only). |
| FR-24 Update book | `PATCH /api/admin/books/{id}` (admin only). |
| FR-25 Deactivate book | The same endpoint with `is_active` set to false. |

`GET /api/admin/books` also lists withdrawn books, so that admins can restore them.

## 2. Web pages

FastAPI serves these from the `frontend/` folder, using plain HTML, CSS and JavaScript.

| Page | Purpose | Who can use it |
|---|---|---|
| `/` | Browse, search and filter books | Everyone |
| `/book.html?id=1` | Book details | Everyone |
| `/login.html` | Log in or create an account | Everyone |
| `/cart.html` | View and change the cart | Customers |
| `/admin.html` | Add, edit, withdraw and restore books | Admins |

The pages are only a convenience. The real access rules are enforced by the API,
so hiding a button is never what protects an action.

## 3. Design decisions

| Decision | Reason |
|---|---|
| A cart does not reserve stock | Otherwise an abandoned cart would block other customers. Stock is reserved when an order is placed (Week 5). |
| The cart shows the current price | The price is only locked in when the order is placed, using `order_items.unit_price`. |
| Cart lines are flagged, not silently removed | If a book is withdrawn or stock falls, the customer sees why. `can_checkout` becomes false. |
| Search treats `%` and `_` as ordinary characters | In SQL `LIKE` these are wildcards, so a search for `%` would otherwise match every book. |
| Book, author and category data is loaded together | One extra query per book would make list pages slower as they grow (the "N+1 query" problem). |
| Admin-only and customer-only endpoints use `require_role` | The same check from Week 3 now protects the cart and book management. |
| Admins are given no cart | Only customers can buy, matching the difference built into `UserFactory`. |

## 4. Handling simultaneous requests

Two requests can change one cart at the same moment, for example a double-click
on **Add to cart**. Each request locks its cart row with `SELECT ... FOR UPDATE`,
so the changes happen one at a time and neither is lost.

The cart item must be read with a lock too. MySQL's default isolation level,
`REPEATABLE READ`, gives each transaction a snapshot from its first ordinary
read. The request has already read the user by this point, so an ordinary read
would return the quantity from before the lock was obtained. A locking read
always returns the latest committed data.

`test_simultaneous_adds_are_all_counted` covers this case.

## 5. Testing

| File | Covers |
|---|---|
| `test_books_api.py` | Paging, search, filtering, withdrawn and out-of-stock books |
| `test_cart_api.py` | Access, exact totals, stock limits, simultaneous adds |
| `test_admin_books_api.py` | Access, validation, editing, withdrawing, duplicate ISBNs |
| `test_frontend.py` | Pages are served and project files are not |

## 6. Suggested demo

1. As a guest, search for `gamma` to show search by author, then filter by category.
2. Click **Add to cart**. As a guest you are sent to the login page.
3. Create an account. You return to the same search, now logged in.
4. Add two books, open the cart, and change a quantity to show the totals update.
5. Type a quantity above the stock to show the error, and that the cart is unchanged.
6. Log out and log in as an admin. Add a book, then withdraw one that is in the
   customer's cart.
7. Log back in as the customer to show the warning on that cart line.
