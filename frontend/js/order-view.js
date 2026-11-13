// Order details shared by the customer's order page and the admin's order page.
import { STATUS_LABELS, api, el, formatDate, money, showToast, statusTag } from "./api.js";

const METHOD_NAMES = { CREDIT_CARD: "Credit card", PAYPAL: "PayPal", BANK_TRANSFER: "Bank transfer" };

function itemLine(item) {
  return el(
    "div",
    { class: "summary-row order-item" },
    el("span", {}, el("strong", {}, item.book.title), ` × ${item.quantity} at ${money(item.unit_price)}`),
    el("span", {}, money(item.line_total))
  );
}

function paymentOutcome(payment) {
  if (payment.status === "SUCCESS") return el("span", { class: "tag" }, `Approved · ${payment.transaction_ref}`);
  if (payment.status === "REFUNDED") return el("span", { class: "tag tag-shipped" }, `Refunded · ${payment.transaction_ref}`);
  return el("span", { class: "tag tag-cancelled" }, `Failed · ${payment.failure_reason}`);
}

function paymentLine(payment) {
  return el(
    "li",
    {},
    el("span", {}, `${METHOD_NAMES[payment.method]} · ${money(payment.amount)} · ${formatDate(payment.created_at)}`),
    " ",
    paymentOutcome(payment)
  );
}

function historyLine(change) {
  return el(
    "li",
    {},
    el("strong", {}, STATUS_LABELS[change.to_status]),
    ` · ${formatDate(change.changed_at)}`,
    change.note ? ` · ${change.note}` : ""
  );
}

export function renderOrderDetails(order) {
  document.title = `Order #${order.id} | Online Bookstore`;
  document.getElementById("order-title").textContent = `Order #${order.id}`;
  document.getElementById("order-status").replaceChildren(statusTag(order.status));
  document.getElementById("order-meta").textContent =
    `Placed ${formatDate(order.created_at)} · ${order.item_count} ${order.item_count === 1 ? "item" : "items"}`;
  document.getElementById("order-items").replaceChildren(...order.items.map(itemLine));
  document.getElementById("order-total").textContent = money(order.total_amount);
  document.getElementById("order-address").textContent = order.shipping_address;
  document.getElementById("payments-section").hidden = order.payments.length === 0;
  document.getElementById("order-payments").replaceChildren(...order.payments.map(paymentLine));
  document.getElementById("order-history").replaceChildren(...order.history.map(historyLine));
}

// Admin actions. Which ones appear depends on order.available_actions, which
// comes from the order's current state on the server.
export const ADMIN_ACTIONS = {
  ship: { label: "Mark shipped", done: "marked as shipped" },
  deliver: { label: "Mark delivered", done: "marked as delivered" },
  cancel: { label: "Cancel order", done: "cancelled", danger: true },
};

export async function runAdminAction(order, action) {
  if (action === "cancel") {
    const refund = order.status === "PAID" ? " The customer will be refunded." : "";
    if (!confirm(`Cancel order #${order.id}?${refund} This can't be undone.`)) return null;
  }
  return api(`/api/admin/orders/${order.id}/${action}`, { method: "POST" });
}

// onDone(updatedOrder, action) runs after a successful action. onError runs
// after a refused one, for example when someone else changed the order first,
// so the page can reload and show the current status.
export function adminActionButtons(order, onDone, { small = false, onError = () => {} } = {}) {
  return order.available_actions
    .filter((action) => action in ADMIN_ACTIONS)
    .map((action) => {
      const { label, danger } = ADMIN_ACTIONS[action];
      const size = small ? " button-small" : "";
      const style = danger ? " button-quiet button-danger" : "";
      const button = el("button", {
        class: `button${size}${style}`,
        type: "button",
        "aria-label": `${label}, order #${order.id}`,
        onclick: async () => {
          button.disabled = true;
          try {
            const updated = await runAdminAction(order, action);
            if (updated) onDone(updated, action);
          } catch (error) {
            showToast(error.message, true);
            onError();
          } finally {
            button.disabled = false;
          }
        },
      }, label);
      return button;
    });
}
