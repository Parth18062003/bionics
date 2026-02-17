import { Task } from "../../api/types"
import { Card } from "../ui/Card"
import { Badge } from "../ui/Badge"
import { StateStepper } from "./StateStepper"
import { cn } from "../../lib/utils"
import { Link } from "@tanstack/react-router"

export function TaskRow({ task }: { task: Task }) {
    // Determine border accent based on state
    // APPROVAL_PENDING, IN_REVIEW -> amber
    // *_FAILED, REJECTED, CANCELLED -> rose
    let variant: "default" | "approval" | "alert" = "default"

    if (["APPROVAL_PENDING", "IN_REVIEW"].includes(task.state)) {
        variant = "approval"
    } else if (task.state.endsWith("_FAILED") || ["REJECTED", "CANCELLED"].includes(task.state)) {
        variant = "alert"
    }

    // Agent ID display
    const agentId = task.agent_id || "—"

    // Relative time (simplified)
    const timeAgo = new Date(task.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    return (
        <Link to="/tasks/$taskId" params={{ taskId: task.id }} className="block">
            <Card variant={variant} className="hover:border-neutral-300 transition-colors cursor-pointer p-0 overflow-hidden">
                <div className="grid grid-cols-12 gap-4 items-center p-4">
                    {/* ID */}
                    <div className="col-span-1 min-w-[60px] font-mono text-xs text-neutral-900 font-medium whitespace-nowrap">
                        {task.id}
                    </div>

                    {/* Description */}
                    <div className="col-span-4 text-sm text-neutral-900 font-medium truncate" title={task.description}>
                        {task.description}
                    </div>

                    {/* Stepper */}
                    <div className="col-span-3">
                        <StateStepper currentState={task.state} />
                        <div className="mt-1 text-[10px] text-neutral-500 font-mono pl-1">
                            {task.state}
                        </div>
                    </div>

                    {/* Risk */}
                    <div className="col-span-1 text-center">
                        <Badge risk={task.risk_level.toLowerCase() as any}>{task.risk_level}</Badge>
                    </div>

                    {/* Env */}
                    <div className="col-span-1 text-center">
                        {task.environment === "PRODUCTION" ? (
                            <Badge variant="outline" className="border-rose-200 text-rose-700 bg-rose-50/50">PROD</Badge>
                        ) : (
                            <Badge variant="secondary" className="bg-neutral-100 text-neutral-600">SBOX</Badge>
                        )}
                    </div>

                    {/* Agent */}
                    <div className="col-span-1 font-mono text-xs text-neutral-500 truncate text-right">
                        {agentId}
                    </div>

                    {/* Time */}
                    <div className="col-span-1 text-xs text-neutral-400 text-right">
                        {timeAgo}
                    </div>
                </div>
            </Card>
        </Link>
    )
}
