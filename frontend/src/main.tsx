import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AuthProvider } from "@/lib/auth-context";
import { AppShell } from "@/App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppShell />
        <Toaster
          theme="dark"
          richColors
          closeButton
          position="top-right"
          toastOptions={{
            classNames: {
              toast:
                "rounded-xl border border-white/10 bg-white/[0.08] text-foreground shadow-glass backdrop-blur-xl font-sans",
            },
          }}
        />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
