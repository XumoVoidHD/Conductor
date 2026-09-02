export const API_BASE = import.meta.env.DEV
  ? ""
  : import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
export const TOKEN_KEY = "conductor_access_token";
export const USER_KEY = "conductor_user";

export interface User {
  id: string;
  username: string;
  email: string;
  trading_nodes: number;
  role?: string;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  module: string;
  slug?: string;
}

export interface TradingNode {
  node_id: string;
  status: string;
  alive: boolean;
  ready: boolean;
  strategy_slug: string;
  strategy_name: string;
  broker_adapter: string;
}

export interface TradeRow {
  node_id: string;
  strategy_name?: string;
  strategy_slug?: string;
  broker_adapter?: string;
  instrument_id?: string;
  side?: string;
  quantity?: string;
  avg_px_open?: string;
  unrealized_pnl?: string;
  order_type?: string;
  status?: string;
  order_bucket?: string;
  price?: string;
  leaves_qty?: string;
  avg_px?: string;
  filled_qty?: string;
  reachable?: boolean;
}

export interface ApiErrorDetail {
  message?: string;
  code?: string;
  node_count?: number;
  max_trading_nodes?: number;
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as ApiErrorDetail).message);
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: { loc?: string[]; msg?: string }) => {
        const loc = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
        return loc ? `${loc}: ${item.msg}` : item.msg;
      })
      .join(" · ");
  }
  return "Request failed";
}

export class ApiError extends Error {
  status: number;
  code?: string;
  quota?: { used: number; max: number };

  constructor(message: string, status: number, detail?: ApiErrorDetail | unknown) {
    super(message);
    this.status = status;
    if (detail && typeof detail === "object" && detail !== null) {
      const d = detail as ApiErrorDetail;
      this.code = d.code;
      if (d.node_count != null) {
        this.quota = {
          used: Number(d.node_count),
          max: Number(d.max_trading_nodes ?? 2),
        };
      }
    }
  }
}

export async function api<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  const auth = token ?? localStorage.getItem(TOKEN_KEY);
  if (auth) headers.Authorization = `Bearer ${auth}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "Cannot reach the API. Start the backend (port 8000) or check VITE_API_BASE.",
      0,
    );
  }
  let body: Record<string, unknown> = {};
  try {
    body = await res.json();
  } catch {
    body = {};
  }

  if (!res.ok) {
    throw new ApiError(formatDetail(body.detail), res.status, body.detail);
  }
  return body as T;
}
