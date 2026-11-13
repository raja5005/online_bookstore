# Week 3: User Module (Factory + Singleton)

## 1. What was built

| Requirement | Result |
|---|---|
| FR-5 Register | `POST /api/auth/register` creates a customer with a unique email. |
| FR-6 Log in | `POST /api/auth/login` checks the password and returns a JWT access token. |
| FR-7 View profile | `GET /api/users/me` returns the logged-in user. |
| FR-8 Role restrictions | `require_role` blocks users without the required role (HTTP 403). |
| NFR-1 Password storage | Only bcrypt hashes are stored. |
| NFR-2 Protected endpoints | A valid JWT is required, otherwise the API returns HTTP 401. |

Two additions support the requirements:

- `POST /api/admin/admins` lets an admin create another admin. It is the first
  endpoint that uses the role restriction.
- `python -m scripts.create_admin` creates the very first admin. It has to be a
  command-line step, because public sign-up can only ever create customers.

## 2. Code layout

| Layer | Folder | Responsibility |
|---|---|---|
| API | `app/api/` | HTTP endpoints, login checks, role checks |
| Schemas | `app/schemas/` | Shape and validation of requests and responses |
| Service | `app/services/` | Business rules for registering and logging in |
| Patterns | `app/patterns/` | Singleton metaclass and `UserFactory` |
| Data | `app/repositories/`, `app/models/` | Database queries and table mappings |
| Core | `app/core/` | Configuration, database connection, security, errors |

A registration request flows through the layers like this:

```text
POST /api/auth/register
  -> UserCreate schema validates the JSON          app/schemas/user.py
  -> register endpoint                             app/api/routes/auth.py
  -> AuthService.register                          app/services/auth_service.py
  -> UserFactory.create_user(CUSTOMER, ...)        app/patterns/user_factory.py
       -> CustomerCreator checks the password,
          hashes it, and builds a Customer + Cart
  -> UserRepository.add, then commit               app/repositories/user_repository.py
  -> UserOut schema removes private fields         app/schemas/user.py
```

## 3. Singleton pattern

**Problem:** the application needs exactly one copy of its configuration, and
one database connection pool. Separate copies could disagree with each other,
and every extra pool would hold open more MySQL connections.

**Solution:** [`SingletonMeta`](../app/patterns/singleton.py) is a metaclass
that intercepts object creation. The first call to the class builds the object
and stores it. Every later call returns that stored object.

| Singleton class | File | What it holds |
|---|---|---|
| `Settings` | `app/core/config.py` | Values from `.env`, read once |
| `DatabaseManager` | `app/core/database.py` | The SQLAlchemy engine and its connection pool |

**Points to explain in the demo:**

- `Settings() is Settings()` is true, no matter where in the code it is called.
- FastAPI runs requests on several threads, so creation is protected by a lock.
  Without one, two simultaneous first calls could each create an object.
- The lock is re-entrant (`RLock`), because `DatabaseManager` creates `Settings`
  while the lock is already held. A plain lock would freeze at that point.
- The engine is a singleton but sessions are not. Each request gets its own
  session, so one request's transaction cannot interfere with another's.

## 4. Factory pattern

**Problem:** customers and admins are created differently. If those rules were
written directly in the endpoints, every place that creates a user would have
to repeat them, and adding a new user type would mean editing all of them.

**Solution:** callers ask [`UserFactory`](../app/patterns/user_factory.py) for a
user by role, and do not need to know how that user is built.

| | `CustomerCreator` | `AdminCreator` |
|---|---|---|
| Object created | `Customer` | `Admin` |
| Minimum password | 8 characters | 12 characters |
| Starts with | An empty cart | No cart |

`UserCreator` is an abstract base class that holds the shared steps: check the
password, build the user, normalize the email and name, and hash the password.
Each subclass supplies only what differs: the password length and `_new_user()`.

**Points to explain in the demo:**

- Both endpoints and the command-line script create users through this one factory.
- Adding a new type, such as `Manager`, needs one new creator class and one new
  entry in `UserFactory._creators`. No endpoint has to change.
- Customers and admins share the `users` table. SQLAlchemy uses the `role`
  column to load each row as the correct class.

## 5. Security decisions

| Decision | Reason |
|---|---|
| Sign-up ignores any `role` sent by the client | Stops people from registering themselves as admins. |
| The same error for a wrong password and an unknown email | Doesn't reveal which emails have accounts. |
| The user is loaded from the database on every request | Deactivating an account or changing a role takes effect immediately. |
| The unique index decides duplicates, not an earlier lookup | Two simultaneous sign-ups cannot both succeed. |
| Passwords are limited to 72 bytes | bcrypt cannot process more than that. |

## 6. Testing

The automated tests in `tests/` run against a real MySQL database, using a
separate `online_bookstore_test` database that is deleted afterwards.

| File | Covers |
|---|---|
| `test_singleton.py` | One instance, thread safety, missing secret key |
| `test_user_factory.py` | Correct type, cart, password rules, hashing |
| `test_auth_api.py` | Registration, login, bad and expired tokens, role restrictions |

## 7. Suggested demo

Open <http://127.0.0.1:8000/docs> and show these steps in Swagger:

1. Register a customer with `POST /api/auth/register`. Add `"role": "ADMIN"` to
   the JSON and point out that the response still says `CUSTOMER`.
2. Click **Authorize** and log in with the email as the username.
3. Call `GET /api/users/me` to show the logged-in profile.
4. Call `POST /api/admin/admins` as the customer and show the 403 response.
5. Log out, authorize as an admin, and repeat step 4 to show it now succeeds.
6. In MySQL, run this query to show hashed passwords, and that only customers
   have carts:

```sql
SELECT u.email, u.role, LEFT(u.password_hash, 7) AS hash_start, c.id AS cart_id
FROM users u LEFT JOIN carts c ON c.user_id = u.id;
```
