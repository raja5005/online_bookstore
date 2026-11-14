# Week 8: Demo Script (about 7 minutes, four presenters)

## Who presents what

| Part | Presenter | Time | On screen |
|---|---|---|---|
| 1. Introduction, architecture and patterns | Rushik Reddy Minkuri | 0:00 to 1:45 | Slides 1–5 |
| 2. Customer journey | Drithi Mandhala | 1:45 to 3:45 | Slide 6, then the shop |
| 3. Admin and data integrity | Lakshman Ega | 3:45 to 5:30 | The shop as admin, Swagger, slide 7 |
| 4. Patterns together, testing and close | Raja Simha Tatikonda | 5:30 to 7:00 | Slides 8–10, terminal |

Each part is about the same length. The assignment is only a suggestion. If you
swap parts, just update the hand-over lines.

Use **one laptop**. Whoever is presenting controls it, and you pass it over at
each hand-over. The speaker notes under each slide name the presenter and
repeat their hand-over line.

## Before the demo (10 minutes beforehand)

1. **Reset to a clean database**, so the first order is #1 and nothing is left
   from testing. This deletes all accounts and orders in `online_bookstore`.

   Run these from the project folder.

   ```bash
   mysql -u root -p -e "DROP DATABASE online_bookstore"
   mysql -u root -p < db/schema.sql
   mysql -u root -p < db/seed.sql
   .venv/bin/python -m scripts.create_admin
   ```

2. **Start the server** and leave its terminal visible. Drithi points at the
   `EMAIL:` lines that appear there.

   ```bash
   .venv/bin/uvicorn app.main:app --reload
   ```

3. **Open browser tabs:**
   - Tab 1: http://127.0.0.1:8000/ for the shop (Drithi, as the customer).
   - Tab 2: a private window on the same address (Lakshman, as the admin).
   - Tab 3: http://127.0.0.1:8000/docs for Swagger (Lakshman).
4. **Open the slides** at the title slide. Present them full screen, or open
   the PowerPoint or PDF copy you downloaded.
5. **Run one test file once**, so the test database is warm and the command is
   in Raja's terminal history:

   ```bash
   .venv/bin/python -m pytest tests/test_order_state.py -q
   ```

6. **Rehearse once together with a timer.** Each person also reads the backup
   slide for their own questions (see "Questions" below).

## Part 1: Rushik Reddy Minkuri (0:00 to 1:45), slides

| Slide | Time | Say |
|---|---|---|
| 1. Cover | 0:00 | "We're Rushik, Drithi, Lakshman and Raja. Our project is an online bookstore: customers browse, keep a cart, order and pay, and admins manage books and ship orders." |
| 2. What the system does | 0:20 | "Three kinds of user: guests, customers and admins. All 26 requirements are met, with 28 documented API endpoints and 358 automated tests." |
| 3. Layered architecture | 0:45 | "Python with FastAPI, MySQL 8, and a plain HTML and JavaScript front end. Each layer depends only on the ones below it, and the patterns have their own folder." |
| 4. Database design | 1:05 | "12 tables. The database enforces its own rules: stock can never go negative, and order items keep the price that was paid." |
| 5. Five design patterns | 1:25 | "Five patterns, each solving a real problem: Factory, Singleton, Strategy, State and Observer." |

**Hand over:** "Drithi will now show the system from a customer's side."

## Part 2: Drithi Mandhala (1:45 to 3:45), the shop in tab 1

Show slide 6 (Live demo) for a moment, then switch to the browser.

| Do | Say |
|---|---|
| Search `gamma`, then pick a category | "Search matches title, author or ISBN." |
| Click **Add to cart** as a guest | "Guests are sent to log in first." |
| **Create account** | "**Factory**: sign-up always creates a customer, which starts with an empty cart." |
| Add 2 copies of *Clean Code*, open **Cart**, change the quantity to 30 | "It refuses more than the 25 in stock, and the cart is unchanged." |
| Set it to 2, enter an address, **Place order** | "One transaction: prices recorded, stock reserved, cart emptied." |
| Point at the terminal's `EMAIL:` line and the **Notifications** badge | "**Observer**: the order announced an event, and two observers reacted." |
| Pay with card `4000 0000 0000 0002` | "**Strategy**: the card strategy declined it. The attempt is recorded, and no notification went out, because nothing changed." |
| Switch to **PayPal**, pay | "A different strategy, the same checkout code. The order is now Paid." |

**Hand over:** "Now Lakshman will take that order through to delivery as an admin."

## Part 3: Lakshman Ega (3:45 to 5:30), tabs 2 and 3, then slide 7

| Do | Say |
|---|---|
| Tab 2: log in as the admin, open **Orders** | "Each row shows only the buttons its status allows." |
| Filter **Paid, ready to ship**, click **Mark shipped** | "**State**: a paid order can ship. A pending one can't." |
| Open the order, click **Mark delivered** | "Delivered is final: no buttons are left." |
| Tab 1: open **Notifications** | "The customer heard about every step." |
| Tab 3, Swagger: `POST /api/orders/1/cancel` as the customer | "Cancelling a delivered order returns 409, *A delivered order cannot be cancelled.* The state refuses it, and nothing changes." |
| Back to the slides: slide 7, *Correct under simultaneous requests* (5:00) | "What if a customer cancels at the very moment an admin ships? Both lock the order, so the second one sees the new status and is refused. The same goes for two people buying the last copy, and a double-clicked Pay button. We force each of these races in a test." |

For the Swagger step, click **Authorize** first and log in with the
customer's email and password.

**Hand over:** "Raja will show how the patterns work together, and how we tested it all."

## Part 4: Raja Simha Tatikonda (5:30 to 7:00), slides and terminal

| Slide | Time | Do and say |
|---|---|---|
| 8. One payment, three patterns | 5:30 | Walk through the four steps: "**State**: may this order be paid? **Strategy**: the processor charges the card. **State**: the pending state moves the order to Paid. **Observer**: that change is published, and the notifiers react. **Singleton** supplies the one database connection underneath it all." |
| 9. Testing | 6:15 | Run `.venv/bin/python -m pytest tests/test_order_state.py -q` live (a few seconds). "358 tests in total, against a real MySQL database. This file tries every action in every status. To make sure the tests can actually fail, we broke the code 50 times on purpose, and they caught every real problem." |
| 10. Summary and next steps | 6:45 | "All 26 requirements are met. Next steps are small because of the patterns: a real payment provider is one more strategy, and text messages are one more observer. Any questions?" |

## Questions

Each person answers questions about their own part. Each topic has a backup
slide after the summary slide.

| Topic | Answered by | Backup slide |
|---|---|---|
| Architecture, database, Singleton | Rushik | 12. Singleton |
| Factory, Strategy, payments | Drithi | 11. Factory, 13. Strategy |
| State, cancelling, simultaneous requests | Lakshman | 14. State |
| Observer, notifications, testing | Raja | 15. Observer |

| Question | Answer | Who |
|---|---|---|
| What is the difference between State and Strategy? | Both use interchangeable classes. With Strategy the caller picks the class, such as the payment method. With State the object's status picks it, and the state moves the order on. | Lakshman |
| Why a metaclass for Singleton? | Any class gets single-instance behavior by declaring `metaclass=SingletonMeta`. A lock makes it safe when requests arrive at the same moment. | Rushik |
| What if two people buy the last copy at once? | The books are locked before stock is checked, so the second order waits and is refused. A test forces this exact situation. | Lakshman |
| How are passwords stored? | Only as bcrypt hashes. Login gives the same error for a wrong password and an unknown email. | Drithi |
| Is any card data stored? | No. Only the method, amount, outcome and a random reference. A test checks the database for the card number. | Drithi |
| How would you add Apple Pay? | One new strategy class and one line registering it. Nothing else changes. | Drithi |
| Why check rules in both the database and the code? | The code gives clear messages. The database is the final safeguard if the code ever has a bug. | Rushik |
| Why are emails sent after the commit? | If the change fails and is rolled back, no email goes out for something that never happened. | Raja |

## If something goes wrong

| Problem | Fix |
|---|---|
| The page says *Something went wrong* | Open `/health`. If the database shows as unavailable, check `DB_PASSWORD` in `.env` and restart the server. |
| *Address already in use* | A server is already running. Use that one, or stop it with Ctrl+C. |
| Login fails after resetting the database | The reset removed all accounts. Run `create_admin` again and register the customer again. |
| Running over time | Lakshman skips the Swagger step, and Raja skips the live test run. Both points are still on the slides. |
| Anything else | The slides include the diagrams, so you can explain the flow without the live site. |
