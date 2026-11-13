import { api, el, formatDate, goToLogin, initPage, money, pager, statusTag } from "./api.js";

const statusLine = document.getElementById("status");
const table = document.getElementById("orders");
const rows = document.getElementById("rows");
const pagerBox = document.getElementById("pager");

function orderRow(order) {
  return el(
    "tr",
    {},
    el("td", {}, el("a", { href: `/order.html?id=${order.id}` }, `Order #${order.id}`)),
    el("td", {}, formatDate(order.created_at)),
    el("td", { class: "numeric" }, String(order.item_count)),
    el("td", { class: "numeric" }, money(order.total_amount)),
    el("td", {}, statusTag(order.status))
  );
}

async function load(page = 1) {
  try {
    const result = await api(`/api/orders?page=${page}&page_size=20`);
    if (result.total === 0) {
      statusLine.replaceChildren("You haven't placed any orders yet. ", el("a", { href: "/" }, "Browse books"));
      return;
    }
    statusLine.hidden = true;
    table.hidden = false;
    rows.replaceChildren(...result.items.map(orderRow));
    pagerBox.replaceChildren(...pager(result.page, result.pages, load));
  } catch (error) {
    statusLine.textContent = error.message;
  }
}

const user = await initPage();
if (!user) {
  goToLogin();
} else if (user.role !== "CUSTOMER") {
  location.href = "/admin.html";
} else {
  load();
}
