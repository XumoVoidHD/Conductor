(() => {
  const API_BASE = window.CONDUCTOR_API_BASE || "http://127.0.0.1:8000";

  const form = document.getElementById("register-form");
  const errorEl = document.getElementById("form-error");
  const submitBtn = document.getElementById("submit-btn");
  const registerPanel = document.getElementById("register-panel");
  const successPanel = document.getElementById("success-panel");
  const userCard = document.getElementById("user-card");
  const againBtn = document.getElementById("again-btn");

  function showError(message) {
    errorEl.hidden = false;
    errorEl.textContent = message;
  }

  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = "";
  }

  function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.classList.toggle("is-loading", loading);
  }

  function formatDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const loc = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
          return loc ? `${loc}: ${item.msg}` : item.msg;
        })
        .join(" · ");
    }
    return "Registration failed.";
  }

  function renderUser(user) {
    const rows = [
      ["Username", user.username],
      ["Email", user.email],
      ["Role", user.role],
      ["Trading nodes", String(user.trading_nodes)],
      ["ID", user.id],
    ];
    userCard.innerHTML = rows
      .map(
        ([label, value]) =>
          `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`,
      )
      .join("");
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const data = new FormData(form);
    const payload = {
      username: String(data.get("username") || "").trim(),
      email: String(data.get("email") || "").trim(),
      password: String(data.get("password") || ""),
    };

    if (payload.username.length < 3) {
      showError("Username must be at least 3 characters.");
      return;
    }
    if (payload.password.length < 8) {
      showError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let body = {};
      try {
        body = await res.json();
      } catch {
        body = {};
      }

      if (!res.ok) {
        showError(formatDetail(body.detail) || `Error ${res.status}`);
        return;
      }

      renderUser(body);
      registerPanel.hidden = true;
      successPanel.hidden = false;
      form.reset();
    } catch {
      showError(
        "Cannot reach the API. Is it running at " + API_BASE + "?",
      );
    } finally {
      setLoading(false);
    }
  });

  againBtn.addEventListener("click", () => {
    successPanel.hidden = true;
    registerPanel.hidden = false;
    clearError();
  });
})();
