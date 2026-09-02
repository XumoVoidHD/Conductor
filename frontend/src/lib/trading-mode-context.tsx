import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type TradingMode = "live" | "paper" | "backtest";

export const TRADING_MODES: { id: TradingMode; label: string }[] = [
  { id: "live", label: "Live" },
  { id: "paper", label: "Paper" },
  { id: "backtest", label: "Backtest" },
];

const STORAGE_KEY = "conductor_trading_mode";

function readStoredMode(): TradingMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "live" || stored === "paper" || stored === "backtest") return stored;
  } catch {
    /* ignore */
  }
  return "live";
}

interface TradingModeContextValue {
  mode: TradingMode;
  setMode: (mode: TradingMode) => void;
}

const TradingModeContext = createContext<TradingModeContextValue | null>(null);

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>(readStoredMode);

  const setMode = useCallback((next: TradingMode) => {
    setModeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(() => ({ mode, setMode }), [mode, setMode]);

  return <TradingModeContext.Provider value={value}>{children}</TradingModeContext.Provider>;
}

export function useTradingMode() {
  const ctx = useContext(TradingModeContext);
  if (!ctx) throw new Error("useTradingMode must be used within TradingModeProvider");
  return ctx;
}
