import { TRADING_MODES, useTradingMode, type TradingMode } from "@/lib/trading-mode-context";
import { cn } from "@/lib/utils";

export function TradingModeSwitcher() {
  const { mode, setMode } = useTradingMode();

  return (
    <div
      className="inline-flex rounded-full border border-white/10 bg-white/[0.05] p-1 shadow-[inset_0_1px_0_hsl(0_0%_100%_/_0.06)] backdrop-blur-md"
      role="tablist"
      aria-label="Trading mode"
    >
      {TRADING_MODES.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={mode === id}
          onClick={() => setMode(id)}
          className={cn(
            "relative min-w-[5.5rem] rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wide transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 cursor-pointer sm:min-w-[6.25rem] sm:px-5 sm:text-[11px]",
            mode === id
              ? "bg-accent text-accent-foreground shadow-glow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function TradingModeLabel({ mode }: { mode: TradingMode }) {
  return TRADING_MODES.find((m) => m.id === mode)?.label ?? mode;
}
