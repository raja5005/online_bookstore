# Online Bookstore System

Capstone project: an online bookstore with catalog browsing, user accounts,
a shopping cart, orders with simulated payment, and book administration.

**Team:** Rushik Reddy Minkuri 700783678, Drithi Mandhala 700783443, Lakshman Ega 700777300, Raja Simha Tatikonda 700786644

**Stack:** Python + FastAPI, MySQL 8, simple HTML/JS frontend.

**Design patterns:** Factory (user creation), Singleton (database connection
and configuration), Strategy (payment methods), State (order lifecycle),
Observer (order notifications).

## Progress

- [x] Week 1: Requirements and use cases ([docs/01_requirements.md](docs/01_requirements.md))
- [x] Week 2: Database design ([docs/02_database_design.md](docs/02_database_design.md))
- [x] Week 3: User module, Factory + Singleton ([docs/03_user_module.md](docs/03_user_module.md))
- [x] Week 4: Book and cart module ([docs/04_book_cart_module.md](docs/04_book_cart_module.md))
- [x] Week 5: Orders + Strategy pattern ([docs/05_orders_payment.md](docs/05_orders_payment.md))
- [x] Week 6: Order state management ([docs/06_order_state.md](docs/06_order_state.md))
- [x] Week 7: Observer + UML diagrams ([docs/07_observer_uml.md](docs/07_observer_uml.md))
- [x] Week 8: Final report and demo
  - Project report: [docs/Online_Bookstore_Project_Report.docx](docs/Online_Bookstore_Project_Report.docx)
  - Demo script: [docs/08_demo_script.md](docs/08_demo_script.md)
  - Diagrams: [docs/diagrams/](docs/diagrams/) (ER, use case and 7 UML diagrams)

## Setup

Run these from the project folder.

**1. Install the dependencies**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**2. Configure the app.** Copy `.env.example` to `.env`, then set `DB_PASSWORD`
to your MySQL password and fill in `SECRET_KEY`. `.env.example` shows how to
generate a key. `.env` is ignored by git.

**3. Create the database**

```bash
mysql -u root -p < db/schema.sql
mysql -u root -p < db/seed.sql
```

This creates a new database named `online_bookstore` with 14 sample books.
To rebuild it from scratch, run `DROP DATABASE online_bookstore;` first.

**4. Create the first admin**

```bash
.venv/bin/python -m scripts.create_admin
```

## Run

```bash
.venv/bin/uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/> for the website, or <http://127.0.0.1:8000/docs>
for Swagger UI. In Swagger, use the **Authorize** button to log in, with your
email as the username.

## Test

```bash
.venv/bin/python -m pytest tests -q
```

Tests use the MySQL login from `.env`. They create a separate database named
`online_bookstore_test`, delete it when finished, and never touch `online_bookstore`.
