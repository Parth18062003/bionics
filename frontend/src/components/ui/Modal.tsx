import * as React from "react"
import { createPortal } from "react-dom"
import { cn } from "../../lib/utils"
import { X, AlertTriangle, AlertCircle } from "lucide-react"
import { Button } from "./Button"

export interface ModalProps {
    isOpen: boolean
    onClose: () => void
    title: string
    children: React.ReactNode
    footer?: React.ReactNode
    variant?: "default" | "warning" | "danger"
    maxWidth?: string
}

export function Modal({
    isOpen,
    onClose,
    title,
    children,
    footer,
    variant = "default",
    maxWidth = "max-w-[480px]",
}: ModalProps) {
    const [mounted, setMounted] = React.useState(false)

    React.useEffect(() => {
        setMounted(true)
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose()
        }
        if (isOpen) {
            document.addEventListener("keydown", handleEscape)
            document.body.style.overflow = "hidden"
        }
        return () => {
            document.removeEventListener("keydown", handleEscape)
            document.body.style.overflow = "unset"
        }
    }, [isOpen, onClose])

    if (!isOpen || !mounted) return null

    // Callout depending on variant ($5.7)
    let Callout = null
    if (variant === "warning") {
        Callout = (
            <div className="mb-4 flex items-start space-x-3 rounded-md border-l-[3px] border-amber-500 bg-amber-50 p-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />
                <div className="text-sm text-amber-900">
                    <p className="font-medium">Warning</p>
                    <p>This action requires attention.</p>
                </div>
            </div>
        )
    } else if (variant === "danger") {
        Callout = (
            <div className="mb-4 flex items-start space-x-3 rounded-md border-l-[3px] border-rose-500 bg-rose-50 p-3">
                <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
                <div className="text-sm text-rose-900">
                    <p className="font-medium">Destructive Action</p>
                    <p>This cannot be undone.</p>
                </div>
            </div>
        )
    }

    return createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop: Black at 40% opacity */}
            <div
                className="fixed inset-0 bg-black/40 transition-opacity"
                onClick={onClose}
                aria-hidden="true"
            />

            {/* Container: White, 480px width, 6px border radius */}
            <div
                className={cn(
                    "relative z-50 w-full bg-white p-6 shadow-lg rounded-md animate-in fade-in zoom-in-95 duration-200",
                    maxWidth
                )}
                role="dialog"
                aria-modal="true"
            >
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-neutral-900 leading-none tracking-tight">
                        {title}
                    </h2>
                    <button
                        onClick={onClose}
                        className="rounded-sm opacity-70 ring-offset-white transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-primary-100 focus:ring-offset-2"
                    >
                        <X className="h-4 w-4" />
                        <span className="sr-only">Close</span>
                    </button>
                </div>

                {Callout}

                <div className="text-sm text-neutral-700">
                    {children}
                </div>

                {footer && (
                    <div className="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2">
                        {footer}
                    </div>
                )}
            </div>
        </div>,
        document.body
    )
}
