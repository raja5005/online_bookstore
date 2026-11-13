# Week 6: Order State Management (State Pattern)

## 1. What was built

| Requirement | Result |
|---|---|
| FR-16 Cancel | Customers cancel with `POST /api/orders/{id}/cancel`, admins with `POST /api/admin/orders/{id}/cancel`. Stock is restored, and a paid order is refunded (simulated). |
| FR-19 Valid changes only | Every status change goes through the State pattern. Invalid changes return HTTP 409 and change nothing. |
| FR-20 History | Every change is recorded with who made it, when, and why. |
| FR-26 Admin orders | `GET /api/admin/orders` lists all orders, filterable by status. Admins mark orders shipped and delivered. |

Every order in the API now includes `available_actions`, the actions its
current state allows. The pages use it to decide which buttons to show.

**New pages:** `/admin-orders.html` (all orders, with a status filter) and
`/admin-order.html?id=…` (one order with its customer and next step). The
customer's order page now has a **Cancel order** panel.

## 2. The order lifecycle

| Status | Allowed actions | Result | Who |
|---|---|---|---|
| `PENDING` | pay | `PAID` | System, after a successful payment |
| | cancel | `CANCELLED`, stock restored | Customer, admin |
| `PAID` | ship | `SHIPPED` | Admin |
| | cancel | `CANCELLED`, stock restored, payment refunded | Customer, admin |
| `SHIPPED` | deliver | `DELIVERED` | Admin |
| `DELIVERED` | none (final) | | |
| `CANCELLED` | none (final) | | |

A refund adds a new `REFUNDED` row to `payments`, so the original successful
payment stays in the record.

## 3. State pattern

**Problem:** whether an action is allowed depends on the order's status, and
what the action does depends on it too. Cancelling a paid order must also
refund it, while cancelling an unpaid one must not. Written as `if status == ...`
checks, these rules would be repeated in every place that changes an order,
and it is easy for one of those places to miss a case.

**Solution:** each status is a class in
[`app/patterns/order_state.py`](../app/patterns/order_state.py).

| Class | Role in the pattern |
|---|---|
| `OrderState` | Abstract state. By default it refuses every action with a clear message. |
| `PendingState`, `PaidState`, `ShippedState`, `DeliveredState`, `CancelledState` | Concrete states. Each overrides only the actions it allows. |
| `OrderLifecycle` | Context. It holds the order and passes each action to the state for the current status. |

```python
lifecycle = OrderLifecycle(order, session)
lifecycle.cancel(actor_id, "Cancelled by customer")
# PendingState.cancel: restore stock, then move to CANCELLED
# PaidState.cancel:    restore stock, refund, then move to CANCELLED
# ShippedState:        refused with "A shipped order cannot be cancelled."
```

Because the final states override nothing, they refuse everything automatically.

**Points to explain in the demo:**

- **State versus Strategy:** both patterns put behavior in interchangeable
  classes. With Strategy (Week 5), the *caller* chooses the class, such as the
  payment method. With State, the *object's own status* chooses it, and the
  state itself moves the order to the next state.
- `OrderLifecycle.move_to()` is the only place a status changes, and it always
  records the change in the history. Week 7's Observer pattern hooks in there
  to send notifications.
- The payment service asks the state first, `"pay" in lifecycle.actions`,
  before charging. No money moves for an order that could not become `PAID`.

## 4. Simultaneous changes

A customer cancelling and an admin shipping the same order at the same moment
must not both succeed. Every action first locks the order row with
`SELECT ... FOR UPDATE`. The second request waits, then reads the new status.
The state for that new status refuses the action if it no longer applies.

The tests force this situation to happen. Each request is paused after reading
the order until both have read it. Without the lock both would act, and the
stock would be restored twice. With the lock the second one is refused.

Locks are always taken in the same order: the order, then books in ID order,
then payments. That way no two requests can wait on each other in a circle.

## 5. Testing

| File | Covers |
|---|---|
| `test_order_state.py` | Every action in every status (20 combinations), with no database |
| `test_order_lifecycle_api.py` | Cancelling, refunds, shipping, delivering, admin access, filtering, simultaneous changes |

## 6. Suggested demo

1. As a customer, place two orders and pay for one.
2. On the unpaid order, click **Cancel order**. It shows Cancelled, and the stock goes back up.
3. Log in as an admin and open **Orders**. Each row shows only the buttons its state allows.
4. Click **Mark shipped**, then open the order and click **Mark delivered**.
   Show the full status history.
5. Show a refusal: in Swagger, call `POST /api/orders/{id}/cancel` on the
   delivered order. The response is `409 A delivered order cannot be cancelled.`
6. Open `app/patterns/order_state.py` and point out that the transition table at
   the top matches the classes below it.
