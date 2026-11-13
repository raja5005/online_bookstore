import { api, initPage, setToken } from "./api.js";

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const errorBox = document.getElementById("form-error");

function destination(role) {
  // Only follow links within this site.
  const next = new URLSearchParams(location.search).get("next") ?? "";
  if (next.startsWith("/") && !next.startsWith("//") && !next.includes("\\")) return next;
  return role === "ADMIN" ? "/admin.html" : "/";
}

function showTab(register) {
  tabLogin.setAttribute("aria-selected", String(!register));
  tabRegister.setAttribute("aria-selected", String(register));
  loginForm.hidden = register;
  registerForm.hidden = !register;
  errorBox.hidden = true;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

async function logIn(email, password) {
  const { access_token: token } = await api("/api/auth/login", { form: { username: email, password }, method: "POST" });
  setToken(token);
  const user = await api("/api/users/me");
  location.href = destination(user.role);
}

async function submit(event, action) {
  event.preventDefault();
  const button = event.target.querySelector("button[type=submit]");
  button.disabled = true;
  errorBox.hidden = true;
  try {
    await action();
  } catch (error) {
    showError(error.message);
    button.disabled = false;
  }
}

tabLogin.addEventListener("click", () => showTab(false));
tabRegister.addEventListener("click", () => showTab(true));

loginForm.addEventListener("submit", (event) =>
  submit(event, () =>
    logIn(document.getElementById("login-email").value, document.getElementById("login-password").value)
  )
);

registerForm.addEventListener("submit", (event) =>
  submit(event, async () => {
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;
    await api("/api/auth/register", {
      method: "POST",
      json: { email, password, full_name: document.getElementById("register-name").value },
    });
    await logIn(email, password);
  })
);

const user = await initPage();
if (user) location.href = destination(user.role);
