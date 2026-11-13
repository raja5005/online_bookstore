import { api, el, goToLogin, initPage, money, showToast } from "./api.js";
import { renderOrderDetails } from "./order-view.js";

const statusLine = document.getElementById("status");
const container = document.getElementById("order");
const paymentPanel = document.getElementById("payment-panel");
const paymentForm = document.getElementById("payment-form");
const paymentError = document.getElementById("payment-error");
const payButton = document.getElementById("pay-button");
const cancelPanel = document.getElementById("cancel-panel");
const cancelText = document.getElementById("cancel-text");
const cancelButton = document.getElementById("cancel-button");

const orderId = new URLSearchParams(location.search).get("id");
let currentOrder = null;

function render(order) {
  currentOrder = order;
  renderOrderDetails(order);

  paymentPanel.hidden = !order.available_actions.includes("pay");
  payButton.textContent = `Pay ${money(order.total_amount)}`;

  cancelPanel.hidden = !order.available_actions.includes("cancel");
  cancelText.textContent =
    order.status === "PAID"
      ? `You can cancel until the order ships. Your payment of ${money(order.total_amount)} will be refunded.`
      : "Nothing has been charged yet. Cancelling releases the books you reserved.";

  statusLine.hidden = true;
  container.hidden = false;
}

function showMethod(method) {
  // Disabled fieldsets are skipped by validation and left out of the form data.
  for (const fieldset of paymentForm.querySelectorAll(".method-fields")) {
    const selected = fieldset.dataset.method === method;
    fieldset.hidden = !selected;
    fieldset.disabled = !selected;
  }
  paymentError.hidden = true;
}

function setUpPaymentForm() {
  const month = document.getElementById("expiry-month");
  for (let m = 1; m <= 12; m += 1) {
    month.append(el("option", { value: String(m) }, String(m).padStart(2, "0")));
  }
  document.getElementById("expiry-year").placeholder = String(new Date().getFullYear() + 1);

  paymentForm.addEventListener("change", (event) => {
    if (event.target.name === "method") showMethod(event.target.value);
  });

  paymentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const details = Object.fromEntries(new FormData(paymentForm));
    for (const key of ["expiry_month", "expiry_year"]) {
      if (key in details) details[key] = Number(details[key]);
    }

    payButton.disabled = true;
    paymentError.hidden = true;
    try {
      const { payment, order } = await api(`/api/orders/${orderId}/payments`, { method: "POST", json: details });
      render(order);
      if (payment.status === "SUCCESS") {
        paymentForm.reset();
        showToast("Payment approved. Thank you for your order!");
      } else {
        paymentError.textContent = `Payment failed: ${payment.failure_reason} You can try again.`;
        paymentError.hidden = false;
      }
    } catch (error) {
      paymentError.textContent = error.message;
      paymentError.hidden = false;
      if (error.status === 409) render(await api(`/api/orders/${orderId}`));
    } finally {
      payButton.disabled = false;
    }
  });
}

cancelButton.addEventListener("click", async () => {
  const refund = currentOrder.status === "PAID" ? " Your payment will be refunded." : "";
  if (!confirm(`Cancel order #${currentOrder.id}?${refund} This can't be undone.`)) return;
  cancelButton.disabled = true;
  try {
    render(await api(`/api/orders/${orderId}/cancel`, { method: "POST" }));
    showToast(currentOrder.payments.some((p) => p.status === "REFUNDED") ? "Order cancelled and refunded." : "Order cancelled.");
  } catch (error) {
    showToast(error.message, true);
    render(await api(`/api/orders/${orderId}`));
  } finally {
    cancelButton.disabled = false;
  }
});

const user = await initPage();
if (!user) {
  goToLogin();
} else if (user.role !== "CUSTOMER") {
  location.href = `/admin-order.html?id=${encodeURIComponent(orderId ?? "")}`;
} else {
  setUpPaymentForm();
  try {
    if (!/^[0-9]+$/.test(orderId ?? "")) throw new Error("This order could not be found.");
    render(await api(`/api/orders/${orderId}`));
  } catch (error) {
    statusLine.textContent = error.message;
    statusLine.append(" ", el("a", { href: "/orders.html" }, "View your orders"));
  }
}
