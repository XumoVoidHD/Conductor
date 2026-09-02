import { Loader2 } from "lucide-react";
import { AmbientBackground } from "@/components/layout/ambient-background";
import { useAuth } from "@/lib/auth-context";
import { TradingModeProvider } from "@/lib/trading-mode-context";
import { AuthPage } from "@/pages/AuthPage";
import { DashboardPage } from "@/pages/DashboardPage";

export function AppShell() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="relative flex min-h-screen flex-col items-center justify-center gap-4">
        <AmbientBackground />
        <div className="glass-strong flex flex-col items-center gap-4 px-10 py-8">
          <Loader2 className="h-8 w-8 animate-spin text-accent" aria-label="Loading" />
          <p className="text-sm text-muted-foreground">Loading session…</p>
        </div>
      </div>
    );
  }

  return user ? (
    <TradingModeProvider>
      <DashboardPage />
    </TradingModeProvider>
  ) : (
    <AuthPage />
  );
}
