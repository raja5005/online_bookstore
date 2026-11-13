import { api, el, formatDate, goToLogin, initPage, money, pager, showToast, statusTag } from "./api.js";
import { ADMIN_ACTIONS, adminActionButtons } from "./order-view.js";

const statusLine = document.getElementById("status");
const rows = document.getElementById("rows");
const pagerBox = document.getElementById("pager");
const filter = document.getElementById("status-filter");

let page = 1;

function orderRow(order) {
  const onDone = (updated, action) => {
    showToast(`Order #${updated.id} ${ADMIN_ACTIONS[action].done}.`);
    load();
  };
  return el(
    "tr",
    {},
    el("td", {}, el("a", { href: `/admin-order.html?id=${order.id}` }, `#${order.id}`)),
    el("td", {}, order.customer.full_name, el("div", { class: "hint" }, order.customer.email)),
    el("td", {}, formatDate(order.created_at)),
    el("td", { class: "numeric" }, money(order.total_amount)),
    el("td", {}, statusTag(order.status)),
    el("td", {}, el("div", { class: "row-actions" }, adminActionButtons(order, onDone, { small: true, onError: load })))
  );
}

async function load() {
  const query = new URLSearchParams({ page, page_size: 20 });
  if (filter.value) query.set("status", filter.value);
  try {
    const result = await api(`/api/admin/orders?${query}`);
    statusLine.textContent = `${result.total} ${result.total === 1 ? "order" : "orders"}`;
    rows.replaceChildren(...result.items.map(orderRow));
    pagerBox.replaceChildren(
      ...pager(result.page, result.pages, (next) => {
        page = next;
        load();
      })
    );
  } catch (error) {
    statusLine.textContent = error.message;
  }
}

filter.addEventListener("change", () => {
  page = 1;
  load();
});

const user = await initPage();
if (!user) {
  goToLogin();
} else if (user.role !== "ADMIN") {
  location.href = "/";
} else {
  load();
}
