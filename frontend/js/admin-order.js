import { api, el, goToLogin, initPage, showToast } from "./api.js";
import { ADMIN_ACTIONS, adminActionButtons, renderOrderDetails } from "./order-view.js";

const NEXT_STEP = {
  PENDING: "Waiting for the customer to pay. You can cancel it if needed.",
  PAID: "Paid and ready to ship.",
  SHIPPED: "On its way. Mark it delivered when it arrives.",
  DELIVERED: "Complete. No further changes are possible.",
  CANCELLED: "Cancelled. No further changes are possible.",
};

const statusLine = document.getElementById("status");
const container = document.getElementById("order");
const orderId = new URLSearchParams(location.search).get("id");

function render(order) {
  renderOrderDetails(order);
  document.getElementById("customer-name").textContent = order.customer.full_name;
  document.getElementById("customer-email").textContent = order.customer.email;
  document.getElementById("next-step").textContent = NEXT_STEP[order.status];
  document.getElementById("actions").replaceChildren(
    ...adminActionButtons(
      order,
      (updated, action) => {
        render(updated);
        showToast(`Order ${ADMIN_ACTIONS[action].done}.`);
      },
      { onError: reload }
    )
  );
  statusLine.hidden = true;
  container.hidden = false;
}

async function reload() {
  try {
    if (!/^[0-9]+$/.test(orderId ?? "")) throw new Error("This order could not be found.");
    render(await api(`/api/admin/orders/${orderId}`));
  } catch (error) {
    statusLine.textContent = error.message;
    statusLine.hidden = false;
    container.hidden = true;
  }
}

const user = await initPage();
if (!user) {
  goToLogin();
} else if (user.role !== "ADMIN") {
  location.href = `/order.html?id=${encodeURIComponent(orderId ?? "")}`;
} else {
  reload();
}
