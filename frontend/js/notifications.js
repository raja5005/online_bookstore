import { api, el, formatDate, goToLogin, initPage, pager, setNotificationCount, showToast } from "./api.js";

const statusLine = document.getElementById("status");
const list = document.getElementById("list");
const pagerBox = document.getElementById("pager");
const markAllButton = document.getElementById("mark-all");

let page = 1;

async function markRead(notification) {
  await api(`/api/notifications/${notification.id}/read`, { method: "POST" });
}

function item(notification) {
  const actions = [];
  if (notification.order_id) {
    actions.push(
      el("a", {
        href: `/order.html?id=${notification.order_id}`,
        onclick: async (event) => {
          // Mark it read before leaving, so the count is right on the next page.
          if (notification.is_read) return;
          event.preventDefault();
          await markRead(notification).catch(() => {});
          location.href = `/order.html?id=${notification.order_id}`;
        },
      }, `View order #${notification.order_id}`)
    );
  }
  if (!notification.is_read) {
    actions.push(
      el("button", {
        class: "link-button",
        type: "button",
        onclick: async () => {
          try {
            await markRead(notification);
            await load();
          } catch (error) {
            showToast(error.message, true);
          }
        },
      }, "Mark as read")
    );
  }

  return el(
    "li",
    { class: notification.is_read ? "notification" : "notification notification-unread" },
    notification.is_read ? null : el("span", { class: "visually-hidden" }, "Unread: "),
    el("p", { class: "notification-message" }, notification.message),
    el("p", { class: "notification-meta" }, formatDate(notification.created_at), ...actions.flatMap((a) => [" · ", a]))
  );
}

async function load() {
  try {
    const result = await api(`/api/notifications?page=${page}&page_size=20`);
    setNotificationCount(result.unread);
    markAllButton.hidden = result.unread === 0;
    if (result.total === 0) {
      statusLine.textContent = "No notifications yet. You'll hear from us here whenever an order changes.";
      list.replaceChildren();
      return;
    }
    statusLine.textContent = result.unread === 0 ? "You're all caught up." : `${result.unread} unread`;
    list.replaceChildren(...result.items.map(item));
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

markAllButton.addEventListener("click", async () => {
  markAllButton.disabled = true;
  try {
    await api("/api/notifications/read-all", { method: "POST" });
    await load();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    markAllButton.disabled = false;
  }
});

const user = await initPage();
if (!user) {
  goToLogin();
} else {
  load();
}
