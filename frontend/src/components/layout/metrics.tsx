import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "accent" | "success" | "warning";
}) {
  const toneClass = {
    default: "text-foreground",
    accent: "text-accent",
    success: "text-success",
    warning: "text-amber-400",
  }[tone];

  return (
    <div className="stat-glass">
      <p className="field-label">{label}</p>
      <p className={cn("mt-2 font-heading text-3xl font-bold tabular-nums tracking-tight", toneClass)}>
        {value}
      </p>
      {hint ? <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function SectionAnchor({ id, children }: { id: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-28 animate-slide-up">
      {children}
    </section>
  );
}
