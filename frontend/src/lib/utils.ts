import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function wsBaseUrl(httpBase: string): string {
  if (!httpBase) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }
  return httpBase.replace(/^http/i, (s) => (s.toLowerCase() === "https" ? "wss" : "ws"));
}

export function sideTone(side?: string): "buy" | "sell" | "neutral" {
  const s = String(side || "").toLowerCase();
  if (s.includes("buy")) return "buy";
  if (s.includes("sell")) return "sell";
  return "neutral";
}

export function statusTone(status?: string): "running" | "ready" | "pending" | "stopped" {
  const s = String(status || "").toLowerCase();
  if (s === "running") return "running";
  if (s === "ready") return "ready";
  if (["starting", "stopping", "restarting", "initializing", "deleting"].includes(s)) {
    return "pending";
  }
  return "stopped";
}
