import * as React from "react"
import { cn } from "../../lib/utils"

interface SegmentedControlProps {
    options: { value: string; label: string }[]
    value: string
    onChange: (value: string) => void
    disabled?: boolean
    className?: string
}

export function SegmentedControl({
    options,
    value,
    onChange,
    disabled,
    className,
}: SegmentedControlProps) {
    return (
        <div className={cn("inline-flex rounded-md border border-neutral-200 bg-white", className)}>
            {options.map((option, index) => {
                const isActive = value === option.value
                return (
                    <button
                        key={option.value}
                        type="button"
                        disabled={disabled}
                        onClick={() => onChange(option.value)}
                        className={cn(
                            "px-4 py-2 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md focus:outline-none focus:ring-2 focus:ring-primary-100 focus:z-10",
                            isActive
                                ? "bg-primary-500 text-white"
                                : "bg-white text-neutral-700 hover:bg-neutral-50",
                            index !== 0 && !isActive && "border-l border-neutral-200", // Divider if not active
                            // If active, it covers the border.
                            isActive && "border-primary-500"
                        )}
                    >
                        {option.label}
                    </button>
                )
            })}
        </div>
    )
}
