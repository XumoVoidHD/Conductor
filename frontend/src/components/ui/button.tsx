import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 cursor-pointer select-none",
  {
    variants: {
      variant: {
        default:
          "border border-accent/30 bg-accent/90 text-accent-foreground shadow-glow-sm hover:border-accent/50 hover:bg-accent hover:shadow-glow active:scale-[0.98]",
        secondary:
          "border border-white/10 bg-white/[0.06] text-foreground backdrop-blur-sm hover:border-white/20 hover:bg-white/[0.1] active:scale-[0.98]",
        outline:
          "border border-white/15 bg-transparent text-foreground hover:border-white/25 hover:bg-white/[0.06] active:scale-[0.98]",
        ghost:
          "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground active:scale-[0.98]",
        destructive:
          "border border-destructive/30 bg-destructive/80 text-destructive-foreground hover:bg-destructive active:scale-[0.98]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-11 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
