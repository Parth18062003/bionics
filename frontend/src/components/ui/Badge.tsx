import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const badgeVariants = cva(
    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
    {
        variants: {
            variant: {
                default: "border-transparent bg-primary-500 text-white hover:bg-primary-600",
                secondary: "border-transparent bg-neutral-100 text-neutral-900 hover:bg-neutral-200/80",
                destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
                outline: "text-neutral-950",
                // Semantic variants from Design System
                info: "border-transparent bg-neutral-50 text-neutral-500", // Slate-500 on Slate-50
                success: "border-transparent bg-emerald-50 text-emerald-700",
                warning: "border-transparent bg-amber-50 text-amber-700", // Waiting state
                error: "border-transparent bg-rose-50 text-rose-700", // Failed state
                queued: "border-neutral-200 bg-white text-neutral-600", // Queued state
            },
            // Risk levels (§5.5)
            risk: {
                low: "border-neutral-200 text-neutral-500 bg-white lowercase",
                medium: "border-amber-300 text-amber-700 bg-white lowercase",
                high: "border-rose-300 text-rose-700 bg-white uppercase font-bold",
                critical: "border-rose-600 bg-rose-600 text-white uppercase font-bold",
                none: "",
            }
        },
        defaultVariants: {
            variant: "default",
            risk: "none",
        },
    }
)

export interface BadgeProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> { }

function Badge({ className, variant, risk, ...props }: BadgeProps) {
    // If risk is provided, use it to override/augment
    return (
        <div className={cn(badgeVariants({ variant, risk }), className)} {...props} />
    )
}

export { Badge, badgeVariants }
