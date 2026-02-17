import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"
import { Loader2 } from "lucide-react"

const buttonVariants = cva(
    "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-100 disabled:pointer-events-none disabled:bg-neutral-100 disabled:text-neutral-300",
    {
        variants: {
            variant: {
                primary: "bg-primary-500 text-white hover:bg-primary-600 border-transparent",
                secondary: "bg-white text-neutral-700 border border-neutral-200 hover:bg-neutral-50",
                destructive: "bg-rose-600 text-white hover:bg-rose-700 border-transparent",
                ghost: "bg-transparent text-primary-500 hover:bg-primary-50 border-transparent",
                outline: "border border-neutral-200 bg-white hover:bg-neutral-100 hover:text-neutral-900", // Extra helpful variant
            },
            size: {
                default: "h-9 px-4 py-2",
                sm: "h-8 rounded-md px-3",
                lg: "h-10 rounded-md px-8",
                icon: "h-9 w-9",
            },
            fullWidth: {
                true: "w-full",
            },
        },
        defaultVariants: {
            variant: "primary",
            size: "default",
            fullWidth: false,
        },
    }
)

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    asChild?: boolean
    isLoading?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, fullWidth, isLoading, children, ...props }, ref) => {
        return (
            <button
                className={cn(buttonVariants({ variant, size, fullWidth, className }))}
                ref={ref}
                disabled={props.disabled || isLoading}
                {...props}
            >
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {children}
            </button>
        )
    }
)
Button.displayName = "Button"

export { Button, buttonVariants }
