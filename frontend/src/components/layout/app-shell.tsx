import type { ReactNode } from "react";
import { Activity, LayoutGrid, LogOut, Server, TrendingUp } from "lucide-react";
import { AmbientBackground } from "@/components/layout/ambient-background";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { id: "strategies", label: "Strategies", icon: LayoutGrid },
  { id: "nodes", label: "Nodes", icon: Server },
  { id: "trades", label: "Trades", icon: TrendingUp },
] as const;

interface AppShellProps {
  username?: string;
  redisOk?: boolean;
  children: ReactNode;
  onLogout: () => void;
}

export function AppShell({ username, redisOk, children, onLogout }: AppShellProps) {
  return (
    <div className="relative min-h-screen">
      <AmbientBackground />

      <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-background/40 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-8">
            <a href="#" className="brand-mark shrink-0 text-2xl">
              Con<span>ductor</span>
            </a>
            <nav className="hidden items-center gap-2 md:flex" aria-label="Sections">
              {NAV.map(({ id, label, icon: Icon }) => (
                <a key={id} href={`#${id}`} className="nav-pill">
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {label}
                </a>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant={redisOk ? "running" : "destructive"} className="hidden sm:inline-flex">
              <Activity className="mr-1.5 h-3 w-3" aria-hidden="true" />
              {redisOk ? "Online" : "Offline"}
            </Badge>
            {username ? (
              <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-sm backdrop-blur-sm sm:flex">
                <span className="h-2 w-2 rounded-full bg-accent shadow-[0_0_8px_hsl(var(--accent)/0.8)]" aria-hidden="true" />
                <span className="font-medium text-foreground">{username}</span>
              </div>
            ) : null}
            <Button variant="ghost" size="sm" onClick={onLogout}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>
      </header>

      <main className={cn("relative mx-auto max-w-[1400px] px-4 py-8 sm:px-6 sm:py-10")}>{children}</main>
    </div>
  );
}

export function PageIntro({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-10 max-w-2xl animate-slide-up">
      <p className="field-label mb-3 text-accent">Control plane</p>
      <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-4xl">
        <span className="gradient-text">{title}</span>
      </h1>
      <p className="mt-3 text-base leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}
