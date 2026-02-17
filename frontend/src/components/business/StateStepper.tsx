import * as React from "react"
import { cn } from "../../lib/utils"
import { Check, X } from "lucide-react"

// Types matching ARCHITECTURE.md
export type TaskState =
    | "SUBMITTED" | "PARSING" | "PARSED" | "PARSE_FAILED"
    | "PLANNING" | "PLANNED"
    | "AGENT_ASSIGNMENT" | "AGENT_ASSIGNED" | "IN_DEVELOPMENT" | "CODE_GENERATED" | "DEV_FAILED"
    | "IN_VALIDATION" | "VALIDATION_PASSED" | "VALIDATION_FAILED"
    | "OPTIMIZATION_PENDING" | "IN_OPTIMIZATION" | "OPTIMIZED"
    | "APPROVAL_PENDING" | "IN_REVIEW" | "APPROVED" | "REJECTED"
    | "DEPLOYING" | "DEPLOYED" | "COMPLETED" | "CANCELLED"

// Phase Definition
const PHASES = [
    { id: "PARSE", label: "PARSE", states: ["SUBMITTED", "PARSING", "PARSED", "PARSE_FAILED"] },
    { id: "PLAN", label: "PLAN", states: ["PLANNING", "PLANNED"] },
    { id: "DEVELOP", label: "DEVELOP", states: ["AGENT_ASSIGNMENT", "AGENT_ASSIGNED", "IN_DEVELOPMENT", "CODE_GENERATED", "DEV_FAILED"] },
    { id: "VALIDATE", label: "VALIDATE", states: ["IN_VALIDATION", "VALIDATION_PASSED", "VALIDATION_FAILED"] },
    { id: "APPROVE", label: "APPROVE", states: ["OPTIMIZATION_PENDING", "IN_OPTIMIZATION", "OPTIMIZED", "APPROVAL_PENDING", "IN_REVIEW", "APPROVED", "REJECTED"] },
    { id: "DEPLOY", label: "DEPLOY", states: ["DEPLOYING", "DEPLOYED", "COMPLETED", "CANCELLED"] },
]

export function StateStepper({ currentState }: { currentState: TaskState }) {
    // Determine active phase index
    const activePhaseIndex = PHASES.findIndex(p => p.states.includes(currentState))

    // Determine if state is terminal failure
    const isFailed = ["PARSE_FAILED", "DEV_FAILED", "VALIDATION_FAILED", "REJECTED", "CANCELLED"].includes(currentState)

    return (
        <div className="flex items-center w-full max-w-[200px] justify-between">
            {PHASES.map((phase, index) => {
                let status: "future" | "current" | "completed" | "failed" = "future"

                if (index < activePhaseIndex) {
                    // Past phases are completed unless we wanted to show failure trail? 
                    // Usually past is success if we are here.
                    status = "completed"
                } else if (index === activePhaseIndex) {
                    status = isFailed ? "failed" : "current"
                } else {
                    status = "future"
                }

                // If the WHOLE process is cancelled/failed, maybe future steps are gray? Yes.

                return (
                    <React.Fragment key={phase.id}>
                        {/* Line connector */}
                        {index > 0 && (
                            <div className={cn(
                                "flex-1 h-[1px] mx-1",
                                status === "completed" ? "bg-primary-500" : "bg-neutral-200"
                            )} />
                        )}

                        {/* Node */}
                        <div className="relative group flex flex-col items-center">
                            <div className={cn(
                                "w-3 h-3 rounded-full flex items-center justify-center transition-all",
                                status === "completed" && "bg-emerald-600",
                                status === "current" && "bg-primary-500 w-3.5 h-3.5 ring-2 ring-primary-100", // "slightly larger 14px" approx
                                status === "failed" && "bg-rose-600",
                                status === "future" && "border border-neutral-300 bg-transparent"
                            )}>
                                {status === "completed" && <Check className="w-2 h-2 text-white" strokeWidth={3} />}
                                {status === "failed" && <X className="w-2 h-2 text-white" strokeWidth={3} />}
                            </div>

                            {/* Label */}
                            <span className={cn(
                                "absolute top-5 text-[10px] tracking-tight uppercase",
                                status === "current" ? "text-neutral-900 font-bold" : "text-neutral-500 font-medium"
                            )}>
                                {phase.label}
                            </span>
                        </div>
                    </React.Fragment>
                )
            })}
        </div>
    )
}
