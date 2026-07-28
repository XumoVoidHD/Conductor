(() => {
  const API_BASE = window.CONDUCTOR_API_BASE || "http://127.0.0.1:8000";
  const TOKEN_KEY = "conductor_access_token";
  const USER_KEY = "conductor_user";

  const authShell = document.getElementById("auth-shell");
  const dashShell = document.getElementById("dash-shell");
  const authBanner = document.getElementById("auth-banner");
  const banner = document.getElementById("banner");
  const statusPill = document.getElementById("status-pill");
  const strategyGrid = document.getElementById("strategy-grid");
  const nodesBody = document.getElementById("nodes-body");
  const userLabel = document.getElementById("user-label");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getStoredUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  }

  function setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function showAuthBanner(message, kind = "error") {
    authBanner.hidden = false;
    authBanner.textContent = message;
    authBanner.classList.toggle("info", kind === "info");
  }

  function clearAuthBanner() {
    authBanner.hidden = true;
    authBanner.textContent = "";
  }

  function showBanner(message, kind = "error") {
    banner.hidden = false;
    banner.textContent = message;
    banner.classList.toggle("info", kind === "info");
  }

  function clearBanner() {
    banner.hidden = true;
    banner.textContent = "";
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
    return "Request failed";
  }

  async function api(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });
    let body = {};
    try {
      body = await res.json();
    } catch {
      body = {};
    }

    if (res.status === 401) {
      clearSession();
      showAuth();
      throw new Error(formatDetail(body.detail) || "Not authenticated");
    }
    if (!res.ok) {
      throw new Error(formatDetail(body.detail) || `HTTP ${res.status}`);
    }
    return body;
  }

  function showAuth() {
    stopNodesPoll();
    authShell.hidden = false;
    dashShell.hidden = true;
  }

  function showDash(user) {
    authShell.hidden = true;
    dashShell.hidden = false;
    const max = user?.trading_nodes ?? "—";
    userLabel.textContent = `${user?.username || "—"} · max nodes ${max}`;
  }

  let nodeQuota = { used: 0, max: 2 };
  let nodesPollTimer = null;
  let cachedNodes = [];
  const NODES_POLL_MS = 10_000;

  function statusClass(status) {
    const s = String(status || "").toLowerCase();
    if (s === "running") return "on";
    if (s === "initializing" || s === "starting" || s === "stopping" || s === "restarting") {
      return "init";
    }
    if (s === "ready") return "ready";
    return "";
  }

  function setOptimisticNodeStatus(nodeId, status) {
    cachedNodes = cachedNodes.map((n) => {
      if (n.node_id !== nodeId) return n;
      return { ...n, status };
    });
    renderNodes(cachedNodes);
  }

  function renderStrategies(strategies) {
    if (!strategies.length) {
      strategyGrid.innerHTML = `<p class="muted">No strategies in catalog</p>`;
      return;
    }
    const atLimit = nodeQuota.used >= nodeQuota.max;
    strategyGrid.innerHTML = strategies
      .map(
        (s) => `
      <article class="card" data-id="${s.id}">
        <h3>${escapeHtml(s.name)}</h3>
        <p>${escapeHtml(s.description)}</p>
        <div class="meta">${escapeHtml(s.module)}</div>
        <button type="button" class="btn-primary" data-deploy="${s.id}" ${atLimit ? "disabled title=\"Node limit reached — delete a node first\"" : ""}>
          Deploy
        </button>
      </article>`,
      )
      .join("");
  }

  function renderNodes(nodes) {
    cachedNodes = Array.isArray(nodes) ? nodes : cachedNodes;
    const head = document.getElementById("nodes-quota");
    if (head) {
      head.textContent = `${nodeQuota.used} / ${nodeQuota.max} slots`;
    }
    if (!cachedNodes.length) {
      nodesBody.innerHTML = `<tr><td colspan="5" class="muted">No nodes for your account</td></tr>`;
      return;
    }
    nodesBody.innerHTML = cachedNodes
      .map((n) => {
        const status = n.status || (n.alive ? "Ready" : "Stopped");
        const strategyLabel = n.strategy_name || n.strategy_slug || "—";
        return `
        <tr>
          <td><code>${escapeHtml(n.node_id)}</code></td>
          <td>${escapeHtml(strategyLabel)}</td>
          <td>
            <span class="alive-dot ${statusClass(status)}"></span>
            ${escapeHtml(status)}
          </td>
          <td>${escapeHtml(n.broker_adapter || "—")}</td>
          <td>
            <div class="actions">
              <button type="button" class="btn-tiny" data-action="run" data-node="${escapeHtml(n.node_id)}">Run</button>
              <button type="button" class="btn-tiny" data-action="stop" data-node="${escapeHtml(n.node_id)}">Stop</button>
              <button type="button" class="btn-tiny" data-action="restart" data-node="${escapeHtml(n.node_id)}">Restart</button>
              <button type="button" class="btn-tiny danger" data-action="delete" data-node="${escapeHtml(n.node_id)}">Delete</button>
            </div>
          </td>
        </tr>`;
      })
      .join("");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function refreshStrategies() {
    const data = await api("/api/v1/dashboard/strategies");
    renderStrategies(data.strategies || []);
  }

  async function refreshNodes() {
    const data = await api("/api/v1/dashboard/nodes");
    const nodes = data.nodes || [];
    nodeQuota = {
      used: Number(data.node_count ?? nodes.length),
      max: Number(data.max_trading_nodes ?? getStoredUser()?.trading_nodes ?? 2),
    };
    renderNodes(nodes);
  }

  function stopNodesPoll() {
    if (nodesPollTimer != null) {
      clearInterval(nodesPollTimer);
      nodesPollTimer = null;
    }
  }

  function startNodesPoll() {
    stopNodesPoll();
    nodesPollTimer = setInterval(() => {
      if (dashShell.hidden) return;
      refreshNodes().catch(() => {});
    }, NODES_POLL_MS);
  }

  function switchTab(tab) {
    const isLogin = tab === "login";
    document.getElementById("tab-login").classList.toggle("is-active", isLogin);
    document.getElementById("tab-register").classList.toggle("is-active", !isLogin);
    loginForm.hidden = !isLogin;
    registerForm.hidden = isLogin;
    clearAuthBanner();
  }

  document.getElementById("tab-login").addEventListener("click", () => switchTab("login"));
  document.getElementById("tab-register").addEventListener("click", () => switchTab("register"));

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAuthBanner();
    const data = new FormData(loginForm);
    const btn = document.getElementById("login-btn");
    btn.disabled = true;
    try {
      const result = await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: String(data.get("username") || "").trim(),
          password: String(data.get("password") || ""),
        }),
      });
      setSession(result.access_token, result.user);
      loginForm.reset();
      await enterDashboard(result.user);
    } catch (err) {
      showAuthBanner(err.message || String(err));
    } finally {
      btn.disabled = false;
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAuthBanner();
    const data = new FormData(registerForm);
    const btn = document.getElementById("register-btn");
    btn.disabled = true;
    try {
      await api("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username: String(data.get("username") || "").trim(),
          email: String(data.get("email") || "").trim(),
          password: String(data.get("password") || ""),
        }),
      });
      showAuthBanner("Account created — sign in.", "info");
      registerForm.reset();
      switchTab("login");
    } catch (err) {
      showAuthBanner(err.message || String(err));
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    stopNodesPoll();
    clearSession();
    showAuth();
    switchTab("login");
  });

  async function refreshStatus() {
    try {
      const data = await api("/api/v1/dashboard/status");
      if (data.redis_ok) {
        statusPill.textContent = `redis ok · ${data.user_id}`;
        statusPill.className = "status-pill ok";
      } else {
        statusPill.textContent = "redis down";
        statusPill.className = "status-pill bad";
      }
    } catch {
      statusPill.textContent = "api unreachable";
      statusPill.className = "status-pill bad";
    }
  }

  strategyGrid.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-deploy]");
    if (!btn) return;
    const strategyId = btn.getAttribute("data-deploy");
    clearBanner();
    btn.disabled = true;
    try {
      const result = await api("/api/v1/dashboard/deploy", {
        method: "POST",
        body: JSON.stringify({ strategy_id: strategyId }),
      });
      showBanner(
        `Deployed ${strategyId} → ${result.node_id || "ok"}. Status will show Initializing until ready.`,
        "info",
      );
      await refreshNodes();
      await refreshStrategies();
    } catch (err) {
      showBanner(err.message || String(err));
    } finally {
      btn.disabled = false;
    }
  });

  nodesBody.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const nodeId = btn.getAttribute("data-node");
    clearBanner();

    // Immediate pending status; final status comes from refresh after confirm
    if (action === "run") {
      setOptimisticNodeStatus(nodeId, "Starting");
    } else if (action === "stop") {
      setOptimisticNodeStatus(nodeId, "Stopping");
    } else if (action === "restart") {
      setOptimisticNodeStatus(nodeId, "Restarting");
    } else if (action === "delete") {
      setOptimisticNodeStatus(nodeId, "Deleting");
    }

    try {
      const result = await api(`/api/v1/dashboard/nodes/${action}`, {
        method: "POST",
        body: JSON.stringify({ node_id: nodeId }),
      });
      const status = result.data?.status || result.message || result.status || action;
      showBanner(`${action}: ${status}`, "info");
      await refreshNodes();
      await refreshStrategies();
    } catch (err) {
      showBanner(err.message || String(err));
      await refreshNodes().catch(() => {});
    }
  });

  document.getElementById("refresh-strategies").addEventListener("click", () => {
    refreshStrategies().catch((err) => showBanner(err.message));
  });
  document.getElementById("refresh-nodes").addEventListener("click", () => {
    refreshNodes()
      .then(() => refreshStrategies())
      .catch((err) => showBanner(err.message));
  });

  async function enterDashboard(user) {
    showDash(user);
    clearBanner();
    await refreshStatus();
    try {
      await refreshNodes();
      await refreshStrategies();
      startNodesPoll();
    } catch (err) {
      showBanner(err.message || String(err));
    }
  }

  (async () => {
    const token = getToken();
    const user = getStoredUser();
    if (!token) {
      showAuth();
      return;
    }
    try {
      const me = await api("/api/v1/auth/me");
      setSession(token, me);
      await enterDashboard(me);
    } catch {
      clearSession();
      showAuth();
    }
  })();
})();
