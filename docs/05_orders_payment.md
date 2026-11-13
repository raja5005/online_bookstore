# Week 5: Orders and the Strategy Pattern

## 1. What was built

| Requirement | Result |
|---|---|
| FR-14 Place order | `POST /api/orders` creates the order, records prices, reserves stock and empties the cart, in one transaction. |
| FR-15 Order history | `GET /api/orders` lists your orders. `GET /api/orders/{id}` shows one in full. |
| FR-17 Pay | `POST /api/orders/{id}/payments` with a credit card, PayPal or bank transfer, all simulated. |
| FR-18 Record attempts | Every attempt is stored. A failure leaves the order `PENDING` so the customer can retry. |
| NFR-3 No card data | Only the method, amount, outcome and a generated reference are stored. |

Status changes are recorded in `order_status_history` from the start: "Order placed"
when the order is created, then "Paid by …" when payment succeeds. Week 6
moves the rules for which changes are allowed into the State pattern.

**New pages:** checkout on the cart page, `/order.html?id=…` with the
payment form, and `/orders.html` with the customer's order history.

## 2. Strategy pattern

**Problem:** each payment method needs different details and has different
rules. A card has a number, an expiry date and a CVV, a bank transfer has a
routing number and account number, and PayPal needs only an email. Writing all
of this as `if method == ...` branches in the checkout code would mean editing
that code, and risking breaking the other methods, every time a method is added.

**Solution:** each method is a separate class with the same `pay()` method, in
[`app/patterns/payment_strategy.py`](../app/patterns/payment_strategy.py).

| Class | Role in the pattern |
|---|---|
| `PaymentStrategy` | Abstract strategy: the shared interface, `pay(amount, details)` |
| `CreditCardPayment`, `PayPalPayment`, `BankTransferPayment` | Concrete strategies, one per method |
| `PaymentProcessor` | Context: runs whichever strategy it is given |
| `PaymentService` | Client: chooses the strategy from the customer's request |

```python
processor = PaymentProcessor.for_method(method)   # picks the strategy
result = processor.charge(order.total_amount, details)
```

`PaymentService` never checks which method it is using. Adding Apple Pay, for
example, needs one new strategy class and one entry in `PAYMENT_STRATEGIES`.

**Points to explain in the demo:**

- Strategy versus Factory: the Factory pattern (Week 3) decides *which object
  to create*. The Strategy pattern decides *which algorithm to run* on
  something that already exists, here the order total.
- The request format is checked first, for example that a card number has
  12–19 digits. A badly formatted request is rejected with HTTP 422 and no
  payment is recorded. The strategy then applies the real rules, such as the
  card checksum and expiry. A refusal at that stage is a genuine payment
  attempt, so it is recorded as `FAILED`.
- The amount always comes from the order, never from the request, so a
  customer cannot pay less than the total.

## 3. Test payment details

Each strategy has a documented way to succeed and to fail, so both outcomes
can be shown. These are also listed under **Test payment details** on the order page.

| Method | Approved | Declined |
|---|---|---|
| Credit card | `4242 4242 4242 4242`, any future expiry, any CVV | `4000 0000 0000 0002`, an expired card, or a number that fails the checksum |
| PayPal | Any email | `declined@example.com` |
| Bank transfer | Routing `011000015`, any account number | An account number ending in `0000`, or an invalid routing number |

## 4. Placing an order safely

| Risk | How it is prevented |
|---|---|
| Two customers buy the last copy | The books are locked (`SELECT ... FOR UPDATE`) before stock is checked. The second order waits, sees the new stock, and is refused. |
| The order is half-written | Every check runs before anything changes. A failure rolls back the whole transaction, so the cart, stock and orders are untouched. |
| A double-click places two orders | The cart is locked. The second request finds it already empty. |
| A double-click pays twice | The order is locked. The second request finds it already paid. |
| Deadlocks | Books are always locked in ID order, so two orders can never wait on each other in a circle. |
| Price changes after ordering | `order_items.unit_price` keeps the price that was paid. |

Free books are not allowed: a book's price must be greater than zero, so every
order has an amount to pay. The database permits zero, but the API is stricter.

## 5. Testing

| File | Covers |
|---|---|
| `test_payment_strategies.py` | Each strategy's rules, checksums, choosing a strategy, and running any strategy |
| `test_orders_api.py` | Placing orders, all-or-nothing behavior, stock, simultaneous orders, history |
| `test_payments_api.py` | Each method approved and declined, retries, no stored card data, double payment |

## 6. Suggested demo

1. As a customer, add two books to the cart, enter an address, and click **Place order**.
2. On the order page, point out the status "Awaiting payment" and that the cart is now empty.
3. Pay with card `4000 0000 0000 0002`. Show the failure message, the failed
   attempt in the list, and that the order is still awaiting payment.
4. Switch to PayPal and pay. The order becomes Paid, and the status history
   shows both steps.
5. Open **Orders** to show the order history.
6. In MySQL, show that no card number was stored:

```sql
SELECT method, amount, status, transaction_ref, failure_reason FROM payments;
```
