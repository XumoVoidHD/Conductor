import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Loader2,
  Play,
  RefreshCw,
  RotateCw,
  Square,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { AppShell, PageIntro } from "@/components/layout/app-shell";
import { SectionAnchor, StatCard } from "@/components/layout/metrics";
import { LogDialog } from "@/components/LogDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError, type Strategy, type TradeRow, type TradingNode } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn, sideTone, statusTone } from "@/lib/utils";

function SideCell({ side }: { side?: string }) {
  const tone = sideTone(side);
  return (
    <span
      className={cn(
        "font-medium",
        tone === "buy" && "text-success",
        tone === "sell" && "text-destructive",
        tone === "neutral" && "text-muted-foreground",
      )}
    >
      {side || "—"}
    </span>
  );
}

function StatusBadge({ status }: { status?: string }) {
  const tone = statusTone(status);
  return <Badge variant={tone === "stopped" ? "stopped" : tone}>{status || "—"}</Badge>;
}

function LoadingRows({ cols }: { cols: number }) {
  return (
    <TableRow>
      <TableCell colSpan={cols} className="h-24 text-center">
        <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" aria-label="Loading" />
      </TableCell>
    </TableRow>
  );
}

export function DashboardPage() {
  const { user, logout } = useAuth();
  const qc = useQueryClient();
  const [filterNode, setFilterNode] = useState("");
  const [filterBroker, setFilterBroker] = useState("");
  const [logNodeId, setLogNodeId] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["status"],
    queryFn: () => api<{ redis_ok: boolean; user_id: string }>("/api/v1/dashboard/status"),
    refetchInterval: 30_000,
  });

  const strategiesQuery = useQuery({
    queryKey: ["strategies"],
    queryFn: () => api<{ strategies: Strategy[] }>("/api/v1/dashboard/strategies"),
    refetchInterval: 15_000,
  });

  const nodesQuery = useQuery({
    queryKey: ["nodes"],
    queryFn: () =>
      api<{ nodes: TradingNode[]; node_count: number; max_trading_nodes: number }>(
        "/api/v1/dashboard/nodes",
      ),
    refetchInterval: 10_000,
  });

  const tradesQuery = useQuery({
    queryKey: ["trades"],
    queryFn: () =>
      api<{ positions: TradeRow[]; orders: TradeRow[]; fills: TradeRow[] }>(
        "/api/v1/dashboard/trades",
      ),
    refetchInterval: 15_000,
  });

  const nodeAction = useMutation({
    mutationFn: ({ action, node_id }: { action: string; node_id: string }) =>
      api(`/api/v1/dashboard/nodes/${action}`, {
        method: "POST",
        body: JSON.stringify({ node_id }),
      }),
    onSuccess: (_, { action }) => {
      toast.success(action.charAt(0).toUpperCase() + action.slice(1));
      void qc.invalidateQueries({ queryKey: ["nodes"] });
      void qc.invalidateQueries({ queryKey: ["trades"] });
      void qc.invalidateQueries({ queryKey: ["strategies"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deploy = useMutation({
    mutationFn: (strategy_id: string) =>
      api<{ node_id?: string }>("/api/v1/dashboard/deploy", {
        method: "POST",
        body: JSON.stringify({ strategy_id }),
      }),
    onSuccess: (data) => {
      toast.success(`Deployed → ${data.node_id || "ok"}`);
      void qc.invalidateQueries({ queryKey: ["nodes"] });
      void qc.invalidateQueries({ queryKey: ["trades"] });
      void qc.invalidateQueries({ queryKey: ["strategies"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const nodes = nodesQuery.data?.nodes ?? [];
  const quotaUsed = nodesQuery.data?.node_count ?? nodes.length;
  const quotaMax = nodesQuery.data?.max_trading_nodes ?? user?.trading_nodes ?? 2;
  const atLimit = quotaUsed >= quotaMax;

  const brokers = useMemo(() => {
    const set = new Set<string>();
    nodes.forEach((n) => n.broker_adapter && set.add(n.broker_adapter));
    tradesQuery.data?.positions.forEach((r) => r.broker_adapter && set.add(r.broker_adapter));
    return [...set].sort();
  }, [nodes, tradesQuery.data]);

  const match = (row: { node_id: string; broker_adapter?: string }) => {
    if (filterNode && row.node_id !== filterNode) return false;
    if (filterBroker && row.broker_adapter !== filterBroker) return false;
    return true;
  };

  const filteredNodes = nodes.filter(match);
  const positions = (tradesQuery.data?.positions ?? []).filter(match);
  const orders = (tradesQuery.data?.orders ?? []).filter(match);
  const fills = (tradesQuery.data?.fills ?? []).filter(match);

  async function handleNodeAction(action: string, nodeId: string) {
    try {
      await nodeAction.mutateAsync({ action, node_id: nodeId });
    } catch (err) {
      if (err instanceof ApiError && (err.code === "node_gone" || err.status === 410)) {
        toast.error(err.message);
        void qc.invalidateQueries({ queryKey: ["nodes"] });
      }
    }
  }

  const strategyCount = strategiesQuery.data?.strategies?.length ?? 0;

  return (
    <AppShell username={user?.username} redisOk={statusQuery.data?.redis_ok} onLogout={logout}>
      <PageIntro
        title="Overview"
        description="Deploy strategies, manage node lifecycle, and monitor live trading activity across your workers."
      />

      <div className="mb-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Node quota"
          value={`${quotaUsed} / ${quotaMax}`}
          hint={atLimit ? "Delete a node to free a slot" : "Stopped nodes still count"}
          tone={atLimit ? "warning" : "default"}
        />
        <StatCard label="Strategies" value={strategyCount} hint="Available in your vault" />
        <StatCard
          label="Open positions"
          value={positions.length}
          hint={`${orders.length} orders · ${fills.length} fills`}
          tone="accent"
        />
        <StatCard
          label="Filtered nodes"
          value={filteredNodes.length}
          hint={filterNode || filterBroker ? "Filters active" : "All workers visible"}
        />
      </div>

      <div className="space-y-10">
        <SectionAnchor id="strategies">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Strategy vault</CardTitle>
                <CardDescription>Deploy a strategy to provision a new trading worker</CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void qc.invalidateQueries({ queryKey: ["strategies"] })}
                disabled={strategiesQuery.isFetching}
              >
                <RefreshCw
                  className={cn("h-3.5 w-3.5", strategiesQuery.isFetching && "animate-spin")}
                  aria-hidden="true"
                />
                Refresh
              </Button>
            </CardHeader>
            <CardContent>
              {strategiesQuery.isLoading ? (
                <div className="flex h-24 items-center justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-label="Loading strategies" />
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {(strategiesQuery.data?.strategies ?? []).map((s) => (
                    <article
                      key={s.id}
                      className="group flex flex-col rounded-xl border border-white/[0.08] bg-white/[0.04] p-5 backdrop-blur-sm transition-all duration-300 hover:border-accent/25 hover:bg-white/[0.07] hover:shadow-glow-sm"
                    >
                      <div className="flex-1">
                        <h4 className="font-heading text-base font-semibold group-hover:text-accent transition-colors">{s.name}</h4>
                        <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">{s.description}</p>
                        <p className="mt-3 font-mono text-[11px] text-muted-foreground/80">{s.module}</p>
                      </div>
                      <Button
                        size="sm"
                        className="mt-4 w-full sm:w-auto"
                        disabled={atLimit || deploy.isPending}
                        onClick={() => deploy.mutate(s.id)}
                        title={atLimit ? "Delete a node to free a slot" : undefined}
                      >
                        {deploy.isPending ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                        ) : null}
                        Deploy worker
                      </Button>
                    </article>
                  ))}
                  {!strategiesQuery.data?.strategies?.length && (
                    <p className="text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
                      No strategies in catalog
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </SectionAnchor>

        <SectionAnchor id="nodes">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Trading nodes</CardTitle>
                <CardDescription>Run, stop, restart, stream logs, or remove workers</CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select value={filterNode} onChange={(e) => setFilterNode(e.target.value)} aria-label="Filter by node">
                  <option value="">All nodes</option>
                  {nodes.map((n) => (
                    <option key={n.node_id} value={n.node_id}>
                      {n.node_id}
                    </option>
                  ))}
                </Select>
                <Select
                  value={filterBroker}
                  onChange={(e) => setFilterBroker(e.target.value)}
                  aria-label="Filter by broker"
                >
                  <option value="">All brokers</option>
                  {brokers.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </Select>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => void qc.invalidateQueries({ queryKey: ["nodes"] })}
                  disabled={nodesQuery.isFetching}
                  aria-label="Refresh nodes"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", nodesQuery.isFetching && "animate-spin")} />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Node</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Broker</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {nodesQuery.isLoading ? (
                    <LoadingRows cols={5} />
                  ) : filteredNodes.length === 0 ? (
                    <TableEmpty colSpan={5}>
                      No nodes{filterNode || filterBroker ? " match filters" : ""}
                    </TableEmpty>
                  ) : (
                    filteredNodes.map((n) => (
                      <TableRow key={n.node_id}>
                        <TableCell>
                          <code className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 font-mono text-[11px] text-accent">
                            {n.node_id}
                          </code>
                        </TableCell>
                        <TableCell>{n.strategy_name || n.strategy_slug}</TableCell>
                        <TableCell>
                          <StatusBadge status={n.status || (n.alive ? "Ready" : "Stopped")} />
                        </TableCell>
                        <TableCell className="text-muted-foreground">{n.broker_adapter || "—"}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap justify-end gap-1">
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => void handleNodeAction("run", n.node_id)}
                              disabled={nodeAction.isPending}
                            >
                              <Play className="h-3 w-3" aria-hidden="true" /> Run
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void handleNodeAction("stop", n.node_id)}
                              disabled={nodeAction.isPending}
                            >
                              <Square className="h-3 w-3" aria-hidden="true" /> Stop
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void handleNodeAction("restart", n.node_id)}
                              disabled={nodeAction.isPending}
                            >
                              <RotateCw className="h-3 w-3" aria-hidden="true" /> Restart
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setLogNodeId(n.node_id)}>
                              <FileText className="h-3 w-3" aria-hidden="true" /> Logs
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => void handleNodeAction("delete", n.node_id)}
                              disabled={nodeAction.isPending}
                            >
                              <Trash2 className="h-3 w-3" aria-hidden="true" /> Delete
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </SectionAnchor>

        <SectionAnchor id="trades">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Live trades</CardTitle>
                <CardDescription>Positions, orders, and fills aggregated from node snapshots</CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void qc.invalidateQueries({ queryKey: ["trades"] })}
                disabled={tradesQuery.isFetching}
              >
                <RefreshCw
                  className={cn("h-3.5 w-3.5", tradesQuery.isFetching && "animate-spin")}
                  aria-hidden="true"
                />
                Refresh
              </Button>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="positions">
                <TabsList>
                  <TabsTrigger value="positions">Positions ({positions.length})</TabsTrigger>
                  <TabsTrigger value="orders">Orders ({orders.length})</TabsTrigger>
                  <TabsTrigger value="fills">Fills ({fills.length})</TabsTrigger>
                </TabsList>

                <TabsContent value="positions">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Node</TableHead>
                        <TableHead>Strategy</TableHead>
                        <TableHead>Instrument</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Avg open</TableHead>
                        <TableHead>Unreal. PnL</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tradesQuery.isLoading ? (
                        <LoadingRows cols={7} />
                      ) : positions.length === 0 ? (
                        <TableEmpty colSpan={7}>No open positions</TableEmpty>
                      ) : (
                        positions.map((p, i) => (
                          <TableRow key={`${p.node_id}-${p.instrument_id}-${i}`}>
                            <TableCell>
                              <code className="data-cell">{p.node_id}</code>
                            </TableCell>
                            <TableCell>{p.strategy_name || p.strategy_slug}</TableCell>
                            <TableCell>
                              <code className="data-cell">{p.instrument_id}</code>
                            </TableCell>
                            <TableCell>
                              <SideCell side={p.side} />
                            </TableCell>
                            <TableCell className="tabular-nums">{p.quantity ?? "—"}</TableCell>
                            <TableCell className="tabular-nums">{p.avg_px_open ?? "—"}</TableCell>
                            <TableCell className="tabular-nums">{p.unrealized_pnl ?? "—"}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TabsContent>

                <TabsContent value="orders">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Node</TableHead>
                        <TableHead>Instrument</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Price</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tradesQuery.isLoading ? (
                        <LoadingRows cols={7} />
                      ) : orders.length === 0 ? (
                        <TableEmpty colSpan={7}>No open orders</TableEmpty>
                      ) : (
                        orders.map((o, i) => (
                          <TableRow key={`${o.node_id}-${o.instrument_id}-${i}`}>
                            <TableCell>
                              <code className="data-cell">{o.node_id}</code>
                            </TableCell>
                            <TableCell>
                              <code className="data-cell">{o.instrument_id}</code>
                            </TableCell>
                            <TableCell>
                              <SideCell side={o.side} />
                            </TableCell>
                            <TableCell>{o.order_type ?? "—"}</TableCell>
                            <TableCell>{o.status ?? o.order_bucket ?? "—"}</TableCell>
                            <TableCell className="tabular-nums">{o.quantity ?? o.leaves_qty ?? "—"}</TableCell>
                            <TableCell className="tabular-nums">{o.price ?? o.avg_px ?? "—"}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TabsContent>

                <TabsContent value="fills">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Node</TableHead>
                        <TableHead>Instrument</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Filled</TableHead>
                        <TableHead>Avg px</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tradesQuery.isLoading ? (
                        <LoadingRows cols={6} />
                      ) : fills.length === 0 ? (
                        <TableEmpty colSpan={6}>No fills yet</TableEmpty>
                      ) : (
                        fills.map((f, i) => (
                          <TableRow key={`${f.node_id}-${f.instrument_id}-${i}`}>
                            <TableCell>
                              <code className="data-cell">{f.node_id}</code>
                            </TableCell>
                            <TableCell>
                              <code className="data-cell">{f.instrument_id}</code>
                            </TableCell>
                            <TableCell>
                              <SideCell side={f.side} />
                            </TableCell>
                            <TableCell className="tabular-nums">{f.filled_qty ?? "—"}</TableCell>
                            <TableCell className="tabular-nums">{f.avg_px ?? "—"}</TableCell>
                            <TableCell>{f.status ?? "—"}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </SectionAnchor>
      </div>

      <LogDialog nodeId={logNodeId} open={!!logNodeId} onOpenChange={(o) => !o && setLogNodeId(null)} />
    </AppShell>
  );
}
