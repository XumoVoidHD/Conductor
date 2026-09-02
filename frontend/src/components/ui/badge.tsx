import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider backdrop-blur-sm",
  {
    variants: {
      variant: {
        default: "border-accent/30 bg-accent/15 text-accent",
        secondary: "border-white/10 bg-white/[0.06] text-muted-foreground",
        running: "border-success/30 bg-success/15 text-success",
        ready: "border-accent/30 bg-accent/10 text-accent",
        pending: "border-amber-400/30 bg-amber-400/10 text-amber-300",
        stopped: "border-white/10 bg-white/[0.04] text-muted-foreground",
        destructive: "border-destructive/30 bg-destructive/15 text-destructive",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
