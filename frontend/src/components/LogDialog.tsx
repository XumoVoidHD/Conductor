import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { API_BASE, TOKEN_KEY } from "@/lib/api";
import { wsBaseUrl } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface LogDialogProps {
  nodeId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LogDialog({ nodeId, open, onOpenChange }: LogDialogProps) {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState("Connecting…");
  const bodyRef = useRef<HTMLPreElement>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!open || !nodeId) return;

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setStatus("Not authenticated");
      return;
    }

    setLines([]);
    setStatus("Loading container logs…");

    const url = `${wsBaseUrl(API_BASE)}/api/v1/dashboard/nodes/${encodeURIComponent(nodeId)}/logs/stream?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    socketRef.current = ws;

    ws.onopen = () => setStatus("Streaming");
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string) as {
          type?: string;
          line?: string;
          error?: string;
        };
        if (payload.error) {
          setLines((prev) => [...prev.slice(-499), `Error: ${payload.error}`]);
          return;
        }
        if (payload.type === "connected") {
          setLines((prev) => [...prev, `Streaming logs for ${nodeId}`]);
          return;
        }
        if (payload.type === "log" && payload.line) {
          setLines((prev) => [...prev.slice(-499), payload.line!]);
        }
      } catch {
        setLines((prev) => [...prev.slice(-499), String(event.data)]);
      }
    };
    ws.onerror = () => setStatus("Connection failed");
    ws.onclose = () => {
      setLines((prev) => [...prev.slice(-499), "— stream closed —"]);
      setStatus("Closed");
    };

    return () => {
      ws.close();
      socketRef.current = null;
    };
  }, [open, nodeId]);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines]);

  const streaming = status === "Streaming";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Node logs
            {streaming ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-success">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" aria-hidden="true" />
                Live
              </span>
            ) : null}
          </DialogTitle>
          <DialogDescription>
            {nodeId ? (
              <>
                <code className="rounded-md border border-white/10 bg-white/[0.05] px-1.5 py-0.5 font-mono text-xs text-accent">
                  {nodeId}
                </code>
                <span className="mx-2 text-white/20">·</span>
                {status}
              </>
            ) : (
              "Select a node"
            )}
          </DialogDescription>
        </DialogHeader>
        <pre
          ref={bodyRef}
          className="max-h-[60vh] overflow-auto border-t border-white/[0.08] bg-black/30 px-6 py-5 font-mono text-[11px] leading-relaxed text-foreground/85 backdrop-blur-sm"
        >
          {lines.length ? (
            lines.join("\n")
          ) : status === "Loading container logs…" ? (
            <span className="inline-flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              {status}
            </span>
          ) : (
            status
          )}
        </pre>
      </DialogContent>
    </Dialog>
  );
}
