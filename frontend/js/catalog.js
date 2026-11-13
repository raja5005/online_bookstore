import { addToCart, api, bookCover, el, goToLogin, initPage, joinAuthors, money, pager, showToast } from "./api.js";

const PAGE_SIZE = 12;

const form = document.getElementById("search-form");
const searchInput = document.getElementById("search");
const categorySelect = document.getElementById("category");
const statusLine = document.getElementById("status");
const grid = document.getElementById("book-grid");
const pagerBox = document.getElementById("pager");

let user = null;
let latestRequest = 0;

function readState() {
  const params = new URLSearchParams(location.search);
  return {
    search: params.get("search") ?? "",
    category: params.get("category") ?? "",
    page: Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1),
  };
}

function navigate(state) {
  const params = new URLSearchParams();
  if (state.search) params.set("search", state.search);
  if (state.category) params.set("category", state.category);
  if (state.page > 1) params.set("page", state.page);
  const query = params.toString();
  history.pushState(null, "", query ? `/?${query}` : "/");
  load();
}

async function handleAdd(book, button) {
  if (!user) {
    goToLogin();
    return;
  }
  button.disabled = true;
  try {
    await addToCart(book.id);
    showToast(`Added "${book.title}" to your cart.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function buyControl(book) {
  if (!book.in_stock) return el("span", { class: "tag tag-off" }, "Out of stock");
  if (user?.role === "ADMIN") return null;
  const button = el("button", { class: "button button-small", onclick: () => handleAdd(book, button) }, "Add to cart");
  return button;
}

function bookCard(book) {
  const href = `/book.html?id=${book.id}`;
  return el(
    "article",
    { class: "book-card" },
    el("a", { class: "cover-link", href, tabIndex: -1, "aria-hidden": "true" }, bookCover(book)),
    el("h2", { class: "book-card-title" }, el("a", { href }, book.title)),
    el("p", { class: "book-card-authors" }, joinAuthors(book.authors)),
    el("div", { class: "book-card-buy" }, el("span", { class: "price" }, money(book.price)), buyControl(book))
  );
}

function statusText(result, state) {
  const count = `${result.total} ${result.total === 1 ? "book" : "books"}`;
  if (result.total === 0) return "No books match your search.";
  return state.search ? `${count} found for "${state.search}"` : count;
}

async function load() {
  const state = readState();
  searchInput.value = state.search;
  categorySelect.value = state.category;

  const query = new URLSearchParams({ page: state.page, page_size: PAGE_SIZE });
  if (state.search) query.set("search", state.search);
  if (state.category) query.set("category_id", state.category);

  const request = ++latestRequest;
  try {
    const result = await api(`/api/books?${query}`);
    if (request !== latestRequest) return;
    statusLine.textContent = statusText(result, state);
    grid.replaceChildren(...result.items.map(bookCard));
    pagerBox.replaceChildren(...pager(result.page, result.pages, (page) => navigate({ ...state, page })));
  } catch (error) {
    if (request !== latestRequest) return;
    statusLine.textContent = error.message;
    grid.replaceChildren();
    pagerBox.replaceChildren();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  navigate({ search: searchInput.value.trim(), category: categorySelect.value, page: 1 });
});

categorySelect.addEventListener("change", () => {
  navigate({ search: searchInput.value.trim(), category: categorySelect.value, page: 1 });
});

window.addEventListener("popstate", load);

user = await initPage();
try {
  const categories = await api("/api/categories");
  categorySelect.append(...categories.map((category) => el("option", { value: String(category.id) }, category.name)));
} catch {
  // The catalog still works without the category filter.
}
load();
