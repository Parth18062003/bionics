import { Badge } from "../ui/Badge"
import { cn } from "../../lib/utils"

export type AgentStatus = "IDLE" | "BUSY" | "ERROR"

export function AgentStatusBadge({ status, className }: { status: AgentStatus, className?: string }) {
    if (status === "IDLE") {
        // Slate outlined pill
        return (
            <Badge variant="outline" className={cn("text-neutral-500 border-neutral-300", className)}>
                IDLE
            </Badge>
        )
    }
    if (status === "BUSY") {
        // Blue outlined pill
        return (
            <Badge variant="outline" className={cn("text-primary-600 border-primary-500 bg-primary-50", className)}>
                BUSY
            </Badge>
        )
    }
    if (status === "ERROR") {
        // Rose filled pill
        return (
            <Badge variant="destructive" className={cn("bg-rose-600 hover:bg-rose-600 border-transparent", className)}>
                ERROR
            </Badge>
        )
    }
    return null
}
