(() => {
  const API_BASE = window.CONDUCTOR_API_BASE || "http://127.0.0.1:8000";
  const TOKEN_KEY = "conductor_access_token";
  const USER_KEY = "conductor_user";

  const authShell = document.getElementById("auth-shell");
  const dashShell = document.getElementById("dash-shell");
  const authBanner = document.getElementById("auth-banner");
  const toastStack = document.getElementById("toast-stack");
  const statusPill = document.getElementById("status-pill");
  const strategyGrid = document.getElementById("strategy-grid");
  const nodesBody = document.getElementById("nodes-body");
  const tradersBody = document.getElementById("traders-body");
  const positionsBody = document.getElementById("positions-body");
  const ordersBody = document.getElementById("orders-body");
  const fillsBody = document.getElementById("fills-body");
  const filterNode = document.getElementById("filter-node");
  const filterBroker = document.getElementById("filter-broker");
  const userLabel = document.getElementById("user-label");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const logPanel = document.getElementById("log-panel");
  const logPanelBody = document.getElementById("log-panel-body");
  const logPanelNode = document.getElementById("log-panel-node");
  const logPanelClose = document.getElementById("log-panel-close");

  const TOAST_TTL_MS = 3500;
  const TRADERS_POLL_MS = 15_000;
  const TRADES_POLL_MS = 15_000;
  const MAX_LOG_LINES = 500;

  let logSocket = null;
  let logLines = [];

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

  function toneForAction(action) {
    const a = String(action || "").toLowerCase();
    if (a === "run" || a === "deploy") return "success";
    if (a === "stop" || a === "restart" || a === "halt") return "warn";
    if (a === "delete") return "danger";
    return "success";
  }

  function dismissToast(el) {
    if (!el || el.classList.contains("leaving")) return;
    el.classList.add("leaving");
    window.setTimeout(() => el.remove(), 200);
  }

  function showToast(message, tone = "success") {
    if (!toastStack) return;
    const el = document.createElement("div");
    el.className = `toast ${tone}`;
    el.setAttribute("role", "status");

    const msg = document.createElement("div");
    msg.className = "toast-msg";
    msg.textContent = message;

    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "Dismiss");
    close.textContent = "×";
    close.addEventListener("click", () => dismissToast(el));

    el.append(msg, close);
    toastStack.appendChild(el);

    let timer = window.setTimeout(() => dismissToast(el), TOAST_TTL_MS);
    el.addEventListener("mouseenter", () => window.clearTimeout(timer));
    el.addEventListener("mouseleave", () => {
      timer = window.setTimeout(() => dismissToast(el), TOAST_TTL_MS);
    });
  }

  function formatDetail(detail) {
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && detail.message) {
      return String(detail.message);
    }
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

  function detailCode(detail) {
    if (detail && typeof detail === "object" && detail.code) {
      return String(detail.code);
    }
    return null;
  }

  function detailQuota(detail) {
    if (!detail || typeof detail !== "object") return null;
    if (detail.node_count == null) return null;
    return {
      used: Number(detail.node_count),
      max: Number(detail.max_trading_nodes ?? nodeQuota.max),
    };
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
      const err = new Error(formatDetail(body.detail) || `HTTP ${res.status}`);
      err.status = res.status;
      err.code = detailCode(body.detail);
      err.quota = detailQuota(body.detail);
      throw err;
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
  let tradersPollTimer = null;
  let tradesPollTimer = null;
  let cachedNodes = [];
  let cachedTraders = [];
  let cachedTrades = { positions: [], orders: [], fills: [] };
  let activeTradeTab = "positions";
  const NODES_POLL_MS = 10_000;
  let filters = { node: "", broker: "" };

  function statusClass(status) {
    const s = String(status || "").toLowerCase();
    if (s === "running") return "on";
    if (s === "initializing" || s === "starting" || s === "stopping" || s === "restarting") {
      return "init";
    }
    if (s === "ready") return "ready";
    if (s === "offline" || s === "error" || s === "stopped" || s === "missing") return "";
    return "";
  }

  function setOptimisticNodeStatus(nodeId, status) {
    cachedNodes = cachedNodes.map((n) => {
      if (n.node_id !== nodeId) return n;
      return { ...n, status };
    });
    renderNodes(cachedNodes);
  }

  function removeNodeFromUi(nodeId, quotaFromServer) {
    cachedNodes = cachedNodes.filter((n) => n.node_id !== nodeId);
    cachedTraders = cachedTraders.filter((t) => t.node_id !== nodeId);
    cachedTrades = {
      positions: cachedTrades.positions.filter((r) => r.node_id !== nodeId),
      orders: cachedTrades.orders.filter((r) => r.node_id !== nodeId),
      fills: cachedTrades.fills.filter((r) => r.node_id !== nodeId),
    };
    if (quotaFromServer) {
      nodeQuota = {
        used: Math.max(0, Number(quotaFromServer.used)),
        max: Number(quotaFromServer.max ?? nodeQuota.max),
      };
    } else {
      nodeQuota = {
        ...nodeQuota,
        used: Math.max(0, nodeQuota.used - 1),
      };
    }
    renderNodes();
    renderTraders();
    renderTrades();
  }

  function isNodeGoneError(err) {
    if (!err) return false;
    if (err.code === "node_gone" || err.status === 410) return true;
    const msg = String(err.message || "").toLowerCase();
    return (
      msg.includes("no longer exists") ||
      msg.includes("is gone") ||
      msg.includes("container") && msg.includes("not found") ||
      (msg.includes("not found") && msg.includes("node"))
    );
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

  function currentFilters() {
    return {
      node: (filterNode && filterNode.value) || filters.node || "",
      broker: (filterBroker && filterBroker.value) || filters.broker || "",
    };
  }

  function matchesFilters(item, f) {
    if (f.node && item.node_id !== f.node) return false;
    if (f.broker && String(item.broker_adapter || "") !== f.broker) return false;
    return true;
  }

  function syncFilterOptions() {
    if (!filterNode || !filterBroker) return;
    const f = currentFilters();
    const nodeIds = [...new Set(cachedNodes.map((n) => n.node_id).filter(Boolean))].sort();
    const brokers = [
      ...new Set(
        [...cachedNodes, ...cachedTraders]
          .map((n) => n.broker_adapter)
          .filter(Boolean),
      ),
    ].sort();

    filterNode.innerHTML =
      `<option value="">All nodes</option>` +
      nodeIds.map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`).join("");
    filterBroker.innerHTML =
      `<option value="">All brokers</option>` +
      brokers
        .map((b) => `<option value="${escapeHtml(b)}">${escapeHtml(b)}</option>`)
        .join("");

    filterNode.value = nodeIds.includes(f.node) ? f.node : "";
    filterBroker.value = brokers.includes(f.broker) ? f.broker : "";
    filters = currentFilters();
  }

  function renderNodes(nodes) {
    if (Array.isArray(nodes)) cachedNodes = nodes;
    const head = document.getElementById("nodes-quota");
    if (head) {
      head.textContent = `${nodeQuota.used} / ${nodeQuota.max} slots`;
    }
    syncFilterOptions();
    const f = currentFilters();
    const visible = cachedNodes.filter((n) => matchesFilters(n, f));
    if (!cachedNodes.length) {
      nodesBody.innerHTML = `<tr><td colspan="5" class="muted">No nodes for your account</td></tr>`;
      return;
    }
    if (!visible.length) {
      nodesBody.innerHTML = `<tr><td colspan="5" class="muted">No nodes match filters</td></tr>`;
      return;
    }
    nodesBody.innerHTML = visible
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
              <button type="button" class="btn-tiny" data-action="logs" data-node="${escapeHtml(n.node_id)}">Logs</button>
              <button type="button" class="btn-tiny danger" data-action="delete" data-node="${escapeHtml(n.node_id)}">Delete</button>
            </div>
          </td>
        </tr>`;
      })
      .join("");
  }

  function renderTraders(traders) {
    if (Array.isArray(traders)) cachedTraders = traders;
    const countEl = document.getElementById("traders-count");
    syncFilterOptions();
    const f = currentFilters();
    const visible = cachedTraders.filter((t) => matchesFilters(t, f));
    if (countEl) {
      countEl.textContent = cachedTraders.length
        ? `${visible.length} / ${cachedTraders.length}`
        : "—";
    }
    if (!tradersBody) return;
    if (!cachedTraders.length) {
      tradersBody.innerHTML = `<tr><td colspan="8" class="muted">No traders yet — deploy a node</td></tr>`;
      return;
    }
    if (!visible.length) {
      tradersBody.innerHTML = `<tr><td colspan="8" class="muted">No traders match filters</td></tr>`;
      return;
    }
    tradersBody.innerHTML = visible
      .map((t) => {
        const state = t.strategy_state || (t.reachable ? "—" : "offline");
        const reach = t.reachable ? "yes" : "no";
        const reachClass = t.reachable ? "on" : "";
        return `
        <tr title="${escapeHtml(t.offline_reason || "")}">
          <td><code>${escapeHtml(t.trader_id || "—")}</code></td>
          <td><code>${escapeHtml(t.node_id)}</code></td>
          <td>${escapeHtml(t.strategy_name || t.strategy_slug || "—")}</td>
          <td>
            <span class="alive-dot ${statusClass(state)}"></span>
            ${escapeHtml(state)}
          </td>
          <td>${escapeHtml(t.broker_adapter || "—")}</td>
          <td>${escapeHtml(t.positions_open ?? 0)}</td>
          <td>${escapeHtml(t.orders_open ?? 0)}</td>
          <td><span class="alive-dot ${reachClass}"></span>${reach}</td>
        </tr>`;
      })
      .join("");
  }

  function applyFilters() {
    filters = currentFilters();
    renderNodes();
    renderTraders();
    renderTrades();
  }

  function sideClass(side) {
    const s = String(side || "").toLowerCase();
    if (s.includes("buy")) return "side-buy";
    if (s.includes("sell")) return "side-sell";
    return "";
  }

  function switchTradeTab(tab) {
    activeTradeTab = tab;
    document.querySelectorAll(".trade-tab").forEach((el) => {
      el.classList.toggle("is-active", el.getAttribute("data-trade-tab") === tab);
    });
    document.getElementById("trades-panel-positions").hidden = tab !== "positions";
    document.getElementById("trades-panel-orders").hidden = tab !== "orders";
    document.getElementById("trades-panel-fills").hidden = tab !== "fills";
  }

  function renderTrades(data) {
    if (data) {
      cachedTrades = {
        positions: data.positions || [],
        orders: data.orders || [],
        fills: data.fills || [],
      };
    }
    const countEl = document.getElementById("trades-count");
    const f = currentFilters();
    const pos = cachedTrades.positions.filter((r) => matchesFilters(r, f));
    const ord = cachedTrades.orders.filter((r) => matchesFilters(r, f));
    const fil = cachedTrades.fills.filter((r) => matchesFilters(r, f));
    if (countEl) {
      countEl.textContent = `${pos.length} pos · ${ord.length} ord · ${fil.length} fills`;
    }

    if (positionsBody) {
      if (!pos.length) {
        positionsBody.innerHTML = `<tr><td colspan="8" class="muted">No open positions${f.node || f.broker ? " match filters" : ""}</td></tr>`;
      } else {
        positionsBody.innerHTML = pos
          .map(
            (p) => `
        <tr title="${p.reachable === false ? "Node offline" : ""}">
          <td><code>${escapeHtml(p.node_id)}</code></td>
          <td>${escapeHtml(p.strategy_name || p.strategy_slug || "—")}</td>
          <td><code>${escapeHtml(p.instrument_id || "—")}</code></td>
          <td><span class="${sideClass(p.side)}">${escapeHtml(p.side || "—")}</span></td>
          <td>${escapeHtml(p.quantity ?? "—")}</td>
          <td>${escapeHtml(p.avg_px_open ?? "—")}</td>
          <td>${escapeHtml(p.unrealized_pnl ?? "—")}</td>
          <td>${escapeHtml(p.broker_adapter || "—")}</td>
        </tr>`,
          )
          .join("");
      }
    }

    if (ordersBody) {
      if (!ord.length) {
        ordersBody.innerHTML = `<tr><td colspan="9" class="muted">No open orders${f.node || f.broker ? " match filters" : ""}</td></tr>`;
      } else {
        ordersBody.innerHTML = ord
          .map(
            (o) => `
        <tr title="${escapeHtml(o.order_bucket || "")}${o.reachable === false ? " · offline" : ""}">
          <td><code>${escapeHtml(o.node_id)}</code></td>
          <td>${escapeHtml(o.strategy_name || o.strategy_slug || "—")}</td>
          <td><code>${escapeHtml(o.instrument_id || "—")}</code></td>
          <td><span class="${sideClass(o.side)}">${escapeHtml(o.side || "—")}</span></td>
          <td>${escapeHtml(o.order_type || "—")}</td>
          <td>${escapeHtml(o.status || o.order_bucket || "—")}</td>
          <td>${escapeHtml(o.quantity ?? o.leaves_qty ?? "—")}</td>
          <td>${escapeHtml(o.price ?? o.avg_px ?? "—")}</td>
          <td>${escapeHtml(o.broker_adapter || "—")}</td>
        </tr>`,
          )
          .join("");
      }
    }

    if (fillsBody) {
      if (!fil.length) {
        fillsBody.innerHTML = `<tr><td colspan="8" class="muted">No fills yet${f.node || f.broker ? " match filters" : ""}</td></tr>`;
      } else {
        fillsBody.innerHTML = fil
          .map(
            (fill) => `
        <tr>
          <td><code>${escapeHtml(fill.node_id)}</code></td>
          <td>${escapeHtml(fill.strategy_name || fill.strategy_slug || "—")}</td>
          <td><code>${escapeHtml(fill.instrument_id || "—")}</code></td>
          <td><span class="${sideClass(fill.side)}">${escapeHtml(fill.side || "—")}</span></td>
          <td>${escapeHtml(fill.filled_qty ?? "—")}</td>
          <td>${escapeHtml(fill.avg_px ?? "—")}</td>
          <td>${escapeHtml(fill.status ?? "—")}</td>
          <td>${escapeHtml(fill.broker_adapter || "—")}</td>
        </tr>`,
          )
          .join("");
      }
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function wsBaseUrl() {
    return API_BASE.replace(/^http/i, (scheme) => (scheme.toLowerCase() === "https" ? "wss" : "ws"));
  }

  function appendLogLine(line, level = "INFO") {
    logLines.push({ line, level });
    if (logLines.length > MAX_LOG_LINES) {
      logLines = logLines.slice(-MAX_LOG_LINES);
    }
    if (!logPanelBody) return;
    const cls =
      level === "ERROR" || level === "CRITICAL"
        ? "log-line-error"
        : level === "WARNING" || level === "WARN"
          ? "log-line-warn"
          : "";
    logPanelBody.insertAdjacentHTML(
      "beforeend",
      `<span class="${cls}">${escapeHtml(line)}</span>\n`,
    );
    logPanelBody.scrollTop = logPanelBody.scrollHeight;
  }

  function closeLogPanel() {
    if (logSocket) {
      logSocket.close();
      logSocket = null;
    }
    logLines = [];
    if (logPanel) logPanel.hidden = true;
    if (logPanelBody) logPanelBody.textContent = "";
  }

  function openLogPanel(nodeId) {
    const token = getToken();
    if (!token) {
      showToast("Sign in to view logs", "error");
      return;
    }
    closeLogPanel();
    if (logPanel) logPanel.hidden = false;
    if (logPanelNode) logPanelNode.textContent = nodeId;
    if (logPanelBody) logPanelBody.textContent = "Loading container logs…\n";

    const url = `${wsBaseUrl()}/api/v1/dashboard/nodes/${encodeURIComponent(nodeId)}/logs/stream?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    logSocket = ws;

    ws.addEventListener("open", () => {
      if (logPanelBody && logPanelBody.textContent === "Loading container logs…\n") {
        logPanelBody.textContent = "";
      }
    });

    ws.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.error) {
          appendLogLine(`Error: ${payload.error}`, "ERROR");
          return;
        }
        if (payload.type === "connected") {
          appendLogLine(`Streaming logs for ${payload.node_id} (docker logs -f)`, "INFO");
          return;
        }
        if (payload.type === "log" && payload.line) {
          appendLogLine(payload.line, payload.level || "INFO");
        }
      } catch {
        appendLogLine(String(event.data), "INFO");
      }
    });

    ws.addEventListener("close", () => {
      if (logSocket === ws) {
        appendLogLine("— stream closed —", "INFO");
        logSocket = null;
      }
    });

    ws.addEventListener("error", () => {
      appendLogLine("WebSocket connection failed", "ERROR");
    });
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

  async function refreshTraders() {
    const data = await api("/api/v1/dashboard/traders");
    renderTraders(data.traders || []);
  }

  async function refreshTrades() {
    const data = await api("/api/v1/dashboard/trades");
    renderTrades(data);
  }

  function stopNodesPoll() {
    if (nodesPollTimer != null) {
      clearInterval(nodesPollTimer);
      nodesPollTimer = null;
    }
    if (tradersPollTimer != null) {
      clearInterval(tradersPollTimer);
      tradersPollTimer = null;
    }
    if (tradesPollTimer != null) {
      clearInterval(tradesPollTimer);
      tradesPollTimer = null;
    }
  }

  function startNodesPoll() {
    stopNodesPoll();
    nodesPollTimer = setInterval(() => {
      if (dashShell.hidden) return;
      refreshNodes().catch(() => {});
    }, NODES_POLL_MS);
    tradersPollTimer = setInterval(() => {
      if (dashShell.hidden) return;
      refreshTraders().catch(() => {});
    }, TRADERS_POLL_MS);
    tradesPollTimer = setInterval(() => {
      if (dashShell.hidden) return;
      refreshTrades().catch(() => {});
    }, TRADES_POLL_MS);
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
    closeLogPanel();
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
    btn.disabled = true;
    try {
      const result = await api("/api/v1/dashboard/deploy", {
        method: "POST",
        body: JSON.stringify({ strategy_id: strategyId }),
      });
      showToast(
        `Deployed ${strategyId} → ${result.node_id || "ok"}`,
        toneForAction("deploy"),
      );
      await refreshNodes();
      await refreshTraders().catch(() => {});
      await refreshTrades().catch(() => {});
      await refreshStrategies();
    } catch (err) {
      showToast(err.message || String(err), "error");
    } finally {
      btn.disabled = false;
    }
  });

  nodesBody.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const nodeId = btn.getAttribute("data-node");

    if (action === "logs") {
      openLogPanel(nodeId);
      return;
    }

    // Immediate pending status; final status comes from refresh after confirm
    if (action === "run") {
      setOptimisticNodeStatus(nodeId, "Starting");
      showToast("Starting...", toneForAction("run"));
    } else if (action === "stop") {
      setOptimisticNodeStatus(nodeId, "Stopping");
      showToast("Stopping...", toneForAction("stop"));
    } else if (action === "restart") {
      setOptimisticNodeStatus(nodeId, "Restarting");
      showToast("Restarting...", toneForAction("restart"));
    } else if (action === "delete") {
      setOptimisticNodeStatus(nodeId, "Deleting");
      showToast("Deleting...", toneForAction("delete"));
    }

    try {
      const result = await api(`/api/v1/dashboard/nodes/${action}`, {
        method: "POST",
        body: JSON.stringify({ node_id: nodeId }),
      });
      const status = result.data?.status || result.message || result.status || "ok";
      const labels = {
        run: "Running",
        stop: "Stopped",
        restart: "Restarted",
        delete: "Deleted",
      };
      showToast(labels[action] || String(status), toneForAction(action));
      if (action === "delete") {
        removeNodeFromUi(nodeId);
      }
      await refreshNodes();
      await refreshTraders().catch(() => {});
      await refreshTrades().catch(() => {});
      await refreshStrategies();
    } catch (err) {
      if (isNodeGoneError(err)) {
        removeNodeFromUi(nodeId, err.quota);
        showToast(
          err.message || `Node ${nodeId} is gone — removed from your list.`,
          "error",
        );
        // Sync counter + deploy buttons from server (soft-delete frees the slot)
        await refreshNodes().catch(() => {});
        await refreshTraders().catch(() => {});
        await refreshStrategies().catch(() => {});
        return;
      }
      showToast(err.message || String(err), "error");
      await refreshNodes().catch(() => {});
    }
  });

  if (filterNode) filterNode.addEventListener("change", applyFilters);
  if (filterBroker) filterBroker.addEventListener("change", applyFilters);

  document.getElementById("refresh-strategies").addEventListener("click", () => {
    refreshStrategies().catch((err) => showToast(err.message, "error"));
  });
  document.getElementById("refresh-nodes").addEventListener("click", () => {
    refreshNodes()
      .then(() => refreshStrategies())
      .catch((err) => showToast(err.message, "error"));
  });
  const refreshTradersBtn = document.getElementById("refresh-traders");
  if (refreshTradersBtn) {
    refreshTradersBtn.addEventListener("click", () => {
      refreshTraders().catch((err) => showToast(err.message, "error"));
    });
  }
  const refreshTradesBtn = document.getElementById("refresh-trades");
  if (refreshTradesBtn) {
    refreshTradesBtn.addEventListener("click", () => {
      refreshTrades().catch((err) => showToast(err.message, "error"));
    });
  }
  document.querySelectorAll(".trade-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      switchTradeTab(btn.getAttribute("data-trade-tab") || "positions");
    });
  });

  if (logPanelClose) {
    logPanelClose.addEventListener("click", closeLogPanel);
  }
  if (logPanel) {
    logPanel.addEventListener("click", (event) => {
      if (event.target === logPanel) closeLogPanel();
    });
  }

  async function enterDashboard(user) {
    showDash(user);
    // Load status + data in parallel so a slow/failed status never blocks the UI
    const results = await Promise.allSettled([
      refreshStatus(),
      refreshNodes(),
      refreshStrategies(),
      refreshTraders(),
      refreshTrades(),
    ]);
    for (const result of results) {
      if (result.status === "rejected") {
        showToast(result.reason?.message || String(result.reason), "error");
      }
    }
    startNodesPoll();
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
