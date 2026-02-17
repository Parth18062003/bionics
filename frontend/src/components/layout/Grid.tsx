import * as React from "react"
import { cn } from "../../lib/utils"

export interface GridProps extends React.HTMLAttributes<HTMLDivElement> {
    as?: React.ElementType
    cols?: number
    gap?: number
}

const Grid = React.forwardRef<HTMLDivElement, GridProps>(
    ({ className, as: Component = "div", cols = 12, gap = 6, children, style, ...props }, ref) => {
        // Use style for dynamic gap/cols to be 100% safe, or just standard classes
        // Design system implies fixed 12 cols, max width 1440, gap 6 (24px)
        return (
            <Component
                ref={ref}
                className={cn(
                    "grid w-full mx-auto max-w-[1440px] px-8", // Global max width and page margins
                    // Fallback to standard classes if matching, otherwise style
                    className
                )}
                style={{
                    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
                    gap: `${gap * 4}px`,
                    ...style
                }}
                {...props}
            >
                {children}
            </Component>
        )
    }
)
Grid.displayName = "Grid"

export { Grid }
