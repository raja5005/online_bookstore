import { addToCart, api, bookCover, el, goToLogin, initPage, money, showToast } from "./api.js";

const statusLine = document.getElementById("status");
const container = document.getElementById("book");

function buySection(book, user) {
  if (!book.in_stock || user?.role === "ADMIN") return null;

  const quantity = el("input", { id: "quantity", type: "number", min: 1, max: Math.min(book.stock, 999), value: 1 });
  const button = el("button", {
    class: "button",
    onclick: async () => {
      if (!user) {
        goToLogin();
        return;
      }
      button.disabled = true;
      try {
        await addToCart(book.id, Number(quantity.value));
        showToast("Added to your cart.");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        button.disabled = false;
      }
    },
  }, "Add to cart");

  return el(
    "div",
    { class: "book-detail-buy" },
    el("div", { class: "field" }, el("label", { for: "quantity" }, "Quantity"), quantity),
    button
  );
}

function render(book, user) {
  document.title = `${book.title} | Online Bookstore`;
  container.replaceChildren(
    el(
      "article",
      { class: "book-detail" },
      el("div", {}, bookCover(book)),
      el(
        "div",
        {},
        el("h1", {}, book.title),
        el("p", { class: "book-detail-authors" }, book.authors.join(", ")),
        el("p", { class: "book-detail-price" }, money(book.price)),
        book.in_stock
          ? el("span", { class: "tag" }, `${book.stock} in stock`)
          : el("span", { class: "tag tag-off" }, "Out of stock"),
        buySection(book, user),
        book.description ? el("p", {}, book.description) : null,
        el("p", { class: "book-facts" }, `${book.category.name} · ISBN ${book.isbn}`)
      )
    )
  );
}

const user = await initPage();
const id = new URLSearchParams(location.search).get("id");

try {
  if (!/^[0-9]+$/.test(id ?? "")) throw new Error("This book could not be found.");
  const book = await api(`/api/books/${id}`);
  statusLine.hidden = true;
  render(book, user);
} catch (error) {
  statusLine.textContent = error.message;
  statusLine.append(" ", el("a", { href: "/" }, "Browse all books"));
}
