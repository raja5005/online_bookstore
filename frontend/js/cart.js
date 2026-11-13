import { api, bookCover, el, goToLogin, initPage, joinAuthors, money, setCartCount, showToast } from "./api.js";

const statusLine = document.getElementById("status");
const layout = document.getElementById("cart");
const linesBox = document.getElementById("cart-lines");
const summaryBox = document.getElementById("cart-summary");

async function change(request) {
  try {
    render(await request());
  } catch (error) {
    showToast(error.message, true);
    render(await api("/api/cart"));
  }
}

function setQuantity(bookId, quantity) {
  return change(() => api(`/api/cart/items/${bookId}`, { method: "PATCH", json: { quantity } }));
}

function removeItem(bookId) {
  return change(() => api(`/api/cart/items/${bookId}`, { method: "DELETE" }));
}

function problemText({ book, quantity }) {
  if (!book.is_active) return "No longer for sale. Please remove it.";
  if (book.stock === 0) return "Now out of stock. Please remove it.";
  return `Only ${book.stock} left. Please reduce the quantity from ${quantity}.`;
}

function cartLine(item) {
  const { book } = item;
  const title = book.is_active ? el("a", { href: `/book.html?id=${book.id}` }, book.title) : book.title;
  const quantity = el("input", {
    type: "number",
    min: 1,
    max: 999,
    value: item.quantity,
    "aria-label": `Quantity of ${book.title}`,
    onchange: () => {
      const value = Number(quantity.value);
      if (!Number.isInteger(value) || value < 1) {
        quantity.value = item.quantity;
        showToast("Quantity must be at least 1. Use Remove to take a book out.", true);
        return;
      }
      setQuantity(book.id, value);
    },
  });

  return el(
    "article",
    { class: "cart-line" },
    bookCover(book),
    el(
      "div",
      {},
      el("p", { class: "cart-line-title" }, title),
      el("p", { class: "cart-line-meta" }, `${joinAuthors(book.authors)} · ${money(book.price)} each`),
      item.available ? null : el("p", { class: "cart-line-problem" }, problemText(item)),
      el("button", { class: "link-button danger", onclick: () => removeItem(book.id) }, "Remove")
    ),
    quantity,
    el("div", { class: "cart-line-total" }, money(item.line_total))
  );
}

function render(cart) {
  setCartCount(cart.item_count);

  if (cart.items.length === 0) {
    layout.hidden = true;
    statusLine.hidden = false;
    statusLine.replaceChildren("Your cart is empty. ", el("a", { href: "/" }, "Browse books"));
    return;
  }

  statusLine.hidden = true;
  layout.hidden = false;
  linesBox.replaceChildren(...cart.items.map(cartLine));
  summaryBox.replaceChildren(
    el("h2", { class: "summary-title" }, "Summary"),
    el(
      "div",
      { class: "summary-row" },
      el("span", {}, `${cart.item_count} ${cart.item_count === 1 ? "item" : "items"}`),
      el("span", {}, money(cart.total))
    ),
    el("div", { class: "summary-row summary-total" }, el("span", {}, "Total"), el("span", {}, money(cart.total)))
  );
  if (!cart.can_checkout) {
    summaryBox.append(el("p", { class: "cart-line-problem" }, "Some books need attention before you can order."));
    return;
  }
  summaryBox.append(checkoutForm());
}

// Kept outside the form so a re-render doesn't lose what the customer typed.
let draftAddress = "";

function checkoutForm() {
  const address = el("textarea", {
    id: "shipping-address",
    rows: 3,
    minLength: 5,
    maxLength: 500,
    required: true,
    autocomplete: "street-address",
    value: draftAddress,
    oninput: () => {
      draftAddress = address.value;
    },
  });
  const button = el("button", { class: "button wide", type: "submit" }, "Place order");

  return el(
    "form",
    {
      class: "checkout",
      onsubmit: async (event) => {
        event.preventDefault();
        button.disabled = true;
        try {
          const order = await api("/api/orders", { method: "POST", json: { shipping_address: address.value } });
          draftAddress = "";
          location.href = `/order.html?id=${order.id}`;
        } catch (error) {
          showToast(error.message, true);
          render(await api("/api/cart"));
        }
      },
    },
    el("div", { class: "field" }, el("label", { for: "shipping-address" }, "Shipping address"), address),
    button,
    el("p", { class: "hint" }, "You'll choose how to pay on the next page. Your books are reserved once the order is placed.")
  );
}

const user = await initPage();
if (!user) {
  goToLogin();
} else if (user.role !== "CUSTOMER") {
  location.href = "/admin.html";
} else {
  try {
    render(await api("/api/cart"));
  } catch (error) {
    statusLine.textContent = error.message;
  }
}
