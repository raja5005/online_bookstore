import { api, el, goToLogin, initPage, money, pager, showToast } from "./api.js";

const PAGE_SIZE = 20;

const statusLine = document.getElementById("status");
const rows = document.getElementById("rows");
const pagerBox = document.getElementById("pager");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search");
const dialog = document.getElementById("book-dialog");
const form = document.getElementById("book-form");
const dialogTitle = document.getElementById("dialog-title");
const errorBox = document.getElementById("form-error");
const categorySelect = document.getElementById("book-category");

let state = { search: "", page: 1 };
let editingId = null;

function field(name) {
  return form.elements[name];
}

function openDialog(book = null) {
  editingId = book?.id ?? null;
  dialogTitle.textContent = book ? "Edit book" : "Add book";
  errorBox.hidden = true;
  field("book_title").value = book?.title ?? "";
  field("authors").value = book?.authors.join("\n") ?? "";
  field("isbn").value = book?.isbn ?? "";
  field("category").value = book ? String(book.category.id) : categorySelect.options[0]?.value ?? "";
  field("price").value = book?.price ?? "";
  field("stock").value = book?.stock ?? 0;
  field("cover").value = book?.cover_url ?? "";
  field("description").value = book?.description ?? "";
  dialog.showModal();
}

function formData() {
  return {
    title: field("book_title").value,
    authors: field("authors").value.split("\n").map((name) => name.trim()).filter(Boolean),
    isbn: field("isbn").value,
    category_id: Number(field("category").value),
    price: field("price").value,
    stock: Number(field("stock").value),
    cover_url: field("cover").value.trim() || null,
    description: field("description").value.trim() || null,
  };
}

async function setActive(book, isActive) {
  try {
    await api(`/api/admin/books/${book.id}`, { method: "PATCH", json: { is_active: isActive } });
    showToast(isActive ? `Restored "${book.title}".` : `Withdrew "${book.title}" from sale.`);
    await load();
  } catch (error) {
    showToast(error.message, true);
  }
}

function bookRow(book) {
  return el(
    "tr",
    { class: book.is_active ? "" : "row-off" },
    el("td", {}, book.title),
    el("td", {}, book.isbn),
    el("td", {}, book.category.name),
    el("td", { class: "numeric" }, money(book.price)),
    el("td", { class: "numeric" }, String(book.stock)),
    el("td", {}, el("span", { class: book.is_active ? "tag" : "tag tag-off" }, book.is_active ? "For sale" : "Withdrawn")),
    el(
      "td",
      {},
      el(
        "div",
        { class: "row-actions" },
        el("button", { class: "link-button", onclick: () => openDialog(book), "aria-label": `Edit ${book.title}` }, "Edit"),
        el(
          "button",
          {
            class: book.is_active ? "link-button danger" : "link-button",
            onclick: () => setActive(book, !book.is_active),
            "aria-label": `${book.is_active ? "Withdraw" : "Restore"} ${book.title}`,
          },
          book.is_active ? "Withdraw" : "Restore"
        )
      )
    )
  );
}

async function load() {
  const query = new URLSearchParams({ page: state.page, page_size: PAGE_SIZE });
  if (state.search) query.set("search", state.search);
  try {
    const result = await api(`/api/admin/books?${query}`);
    statusLine.textContent = `${result.total} ${result.total === 1 ? "book" : "books"}`;
    rows.replaceChildren(...result.items.map(bookRow));
    pagerBox.replaceChildren(
      ...pager(result.page, result.pages, (page) => {
        state = { ...state, page };
        load();
      })
    );
  } catch (error) {
    statusLine.textContent = error.message;
  }
}

document.getElementById("add-book").addEventListener("click", () => openDialog());
document.getElementById("cancel").addEventListener("click", () => dialog.close());

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state = { search: searchInput.value.trim(), page: 1 };
  load();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = form.querySelector("button[type=submit]");
  submit.disabled = true;
  errorBox.hidden = true;
  try {
    if (editingId === null) {
      await api("/api/admin/books", { method: "POST", json: formData() });
      showToast("Book added.");
    } else {
      await api(`/api/admin/books/${editingId}`, { method: "PATCH", json: formData() });
      showToast("Book updated.");
    }
    dialog.close();
    await load();
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    submit.disabled = false;
  }
});

const user = await initPage();
if (!user) {
  goToLogin();
} else if (user.role !== "ADMIN") {
  location.href = "/";
} else {
  try {
    const categories = await api("/api/categories");
    categorySelect.append(...categories.map((category) => el("option", { value: String(category.id) }, category.name)));
    await load();
  } catch (error) {
    statusLine.textContent = error.message;
  }
}
