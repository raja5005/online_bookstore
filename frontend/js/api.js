// Shared helpers: API calls, login state, page header and small UI pieces.
// Text always goes through el() or textContent, so data from the API is never
// interpreted as HTML.

const TOKEN_KEY = "bookstore_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing is stored if storage is unavailable.
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function errorMessage(body) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail) && body.detail[0]) {
    const { loc, msg } = body.detail[0];
    const field = loc?.[loc.length - 1];
    const text = msg.replace(/^Value error, /, "");
    return typeof field === "string" && field !== "body" ? `${field.replace(/_/g, " ")}: ${text}` : text;
  }
  return "Something went wrong. Please try again.";
}

export async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = new URLSearchParams(form);
  }

  let response;
  try {
    response = await fetch(path, { method, headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the server. Is it running?");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && token) clearToken();
    throw new ApiError(response.status, errorMessage(data));
  }
  return data;
}

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  node.append(...children.flat().filter((child) => child !== null && child !== undefined && child !== false));
  return node;
}

export function money(value) {
  return `$${Number(value).toFixed(2)}`;
}

export const STATUS_LABELS = {
  PENDING: "Awaiting payment",
  PAID: "Paid",
  SHIPPED: "Shipped",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
};

export function statusTag(status) {
  return el("span", { class: `tag tag-${status.toLowerCase()}` }, STATUS_LABELS[status] ?? status);
}

export function formatDate(value) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function joinAuthors(authors) {
  if (authors.length <= 2) return authors.join(" and ");
  return `${authors[0]} and ${authors.length - 1} others`;
}

export function bookCover(book) {
  if (book.cover_url) {
    return el("img", { class: "cover", src: book.cover_url, alt: "", loading: "lazy" });
  }
  return el(
    "div",
    { class: `cover cover-art cover-${book.category.id % 5}`, "aria-hidden": "true" },
    el("span", { class: "cover-art-title" }, book.title),
    el("span", { class: "cover-art-author" }, book.authors[0] ?? "")
  );
}

export function pager(page, pages, goTo) {
  if (pages <= 1) return [];
  return [
    el("button", { class: "button button-quiet button-small", disabled: page <= 1, onclick: () => goTo(page - 1) }, "Previous"),
    el("span", {}, `Page ${page} of ${pages}`),
    el("button", { class: "button button-quiet button-small", disabled: page >= pages, onclick: () => goTo(page + 1) }, "Next"),
  ];
}

let toastTimer;

export function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = isError ? "toast toast-error" : "toast";
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 3500);
}

export function goToLogin() {
  const next = encodeURIComponent(location.pathname + location.search);
  location.href = `/login.html?next=${next}`;
}

export function setCartCount(count) {
  const badge = document.getElementById("cart-count");
  if (!badge) return;
  badge.textContent = count;
  badge.hidden = count === 0;
}

async function currentUser() {
  if (!getToken()) return null;
  try {
    return await api("/api/users/me");
  } catch {
    return null;
  }
}

function renderHeader(user) {
  const links = [el("a", { href: "/" }, "Books")];
  if (user?.role === "CUSTOMER") {
    links.push(el("a", { href: "/cart.html" }, "Cart", el("span", { id: "cart-count", class: "count", hidden: true }, "0")));
    links.push(el("a", { href: "/orders.html" }, "Orders"));
    links.push(
      el(
        "a",
        { href: "/notifications.html" },
        "Notifications",
        el("span", { id: "notification-count", class: "count", hidden: true }, "0")
      )
    );
  }
  if (user?.role === "ADMIN") {
    links.push(el("a", { href: "/admin.html" }, "Manage books"));
    links.push(el("a", { href: "/admin-orders.html" }, "Orders"));
  }

  const account = user
    ? [
        el("span", {}, user.full_name),
        el("button", {
          class: "link-button",
          onclick: () => {
            clearToken();
            location.href = "/";
          },
        }, "Log out"),
      ]
    : [el("a", { class: "button button-small", href: "/login.html" }, "Log in")];

  document.getElementById("site-header").replaceChildren(
    el(
      "div",
      { class: "site-header-inner" },
      el("a", { class: "brand", href: "/" }, "Online Bookstore"),
      el("nav", { class: "site-nav", "aria-label": "Main" }, links),
      el("div", { class: "site-account" }, account)
    )
  );
}

// Every page calls this first. It draws the header and returns the logged-in
// user, or null for a guest.
export async function initPage() {
  const user = await currentUser();
  renderHeader(user);
  if (user?.role === "CUSTOMER") {
    api("/api/cart").then((cart) => setCartCount(cart.item_count)).catch(() => {});
    api("/api/notifications?page_size=1").then((page) => setNotificationCount(page.unread)).catch(() => {});
  }
  return user;
}

export function setNotificationCount(count) {
  const badge = document.getElementById("notification-count");
  if (!badge) return;
  badge.textContent = count;
  badge.hidden = count === 0;
  badge.setAttribute("aria-label", `${count} unread`);
}

export async function addToCart(bookId, quantity = 1) {
  const cart = await api("/api/cart/items", { method: "POST", json: { book_id: bookId, quantity } });
  setCartCount(cart.item_count);
  return cart;
}
