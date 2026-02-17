import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { TaskRow } from '../components/business/TaskRow'
import { StateStepper } from '../components/business/StateStepper'
import { Badge } from '../components/ui/Badge'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Grid } from '../components/layout/Grid'
import { CheckCircle2, Circle, AlertTriangle, FileText, Code, Database, Clock } from 'lucide-react'
import { api } from '../api/client'
import { useState } from 'react'

export const Route = createFileRoute('/tasks/$taskId/')({
    component: TaskDetailPage,
    loader: async ({ params }) => {
        try {
            const task = await api.getTask(params.taskId)
            return { task }
        } catch (e) {
            throw e
        }
    },
})

function TaskDetailPage() {
    const { task } = Route.useLoaderData()
    const navigate = useNavigate()
    const [isCancelling, setIsCancelling] = useState(false)

    const handleCancel = async () => {
        if (!confirm("Are you sure you want to cancel this task?")) return
        setIsCancelling(true)
        try {
            await api.updateTaskState(task.id, 'cancel')
            navigate({ to: '.' }) // Refresh
        } catch (e) {
            alert("Failed to cancel")
        } finally {
            setIsCancelling(false)
        }
    }

    return (
        <div className="space-y-6 pb-20">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-neutral-500">
                <Link to="/" className="hover:text-neutral-900">All Tasks</Link>
                <span>/</span>
                <span className="font-medium text-neutral-900">{task.id}</span>
            </div>

            {/* Task Header */}
            <Card>
                <div className="p-6 space-y-4">
                    <div className="flex items-start justify-between">
                        <div className="space-y-1">
                            <div className="flex items-center gap-3">
                                <h1 className="text-2xl font-bold font-mono text-neutral-900">{task.id}</h1>
                                <Badge variant="outline" className="text-xs">{task.state}</Badge>
                            </div>
                            <h2 className="text-lg font-medium text-neutral-900">{task.description}</h2>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                            {task.environment === 'PRODUCTION' ? (
                                <Badge variant="outline" className="border-rose-200 text-rose-700 bg-rose-50">PRODUCTION</Badge>
                            ) : (
                                <Badge variant="secondary">SANDBOX</Badge>
                            )}
                            <div className="flex items-center gap-2 text-xs text-neutral-500">
                                <span>{task.agent_id || "Unassigned"}</span>
                                <span>•</span>
                                <span>{new Date(task.updated_at).toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Stepper Section */}
                <div className="border-t border-neutral-200 p-6 bg-neutral-50/50">
                    <div className="max-w-3xl mx-auto py-2">
                        <div className="w-full flex justify-center">
                            <StateStepper currentState={task.state} />
                        </div>
                    </div>
                </div>
            </Card>

            {(task.state === 'APPROVAL_PENDING' || task.state === 'IN_REVIEW') && (
                <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-md flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <AlertTriangle className="h-5 w-5 text-amber-600" />
                        <div>
                            <p className="text-sm font-medium text-amber-900">Human Approval Required</p>
                            <p className="text-xs text-amber-700">This task is paused waiting for your review.</p>
                        </div>
                    </div>
                    <Link to="/tasks/$taskId/review" params={{ taskId: task.id }}>
                        <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white border-transparent">
                            Review & Approve
                        </Button>
                    </Link>
                </div>
            )}

            <Grid className="px-0 max-w-none" gap={6}>
                {/* Left: Activity Log */}
                <div className="col-span-12 lg:col-span-7 space-y-4">
                    <h3 className="text-sm font-semibold text-neutral-900 uppercase tracking-wide">Agent Activity</h3>
                    <div className="space-y-4 font-mono text-sm">
                        {task.logs && task.logs.length > 0 ? (
                            task.logs.map((log, i) => (
                                <div key={i} className="flex gap-4 group">
                                    <div className="text-xs text-neutral-400 w-[100px] shrink-0 pt-0.5">
                                        {new Date(log.timestamp).toLocaleTimeString()}
                                    </div>
                                    <div className="space-y-1">
                                        <div className="text-neutral-700">
                                            <span className="text-neutral-500 mr-2">[{log.agent_id || "SYSTEM"}]</span>
                                            {log.message}
                                        </div>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-neutral-400 italic">No activity logs yet.</div>
                        )}

                        {/* Live indicator if active */}
                        {!['COMPLETED', 'FAILED', 'CANCELLED'].some(s => task.state.includes(s)) && (
                            <div className="flex gap-4 items-center animate-pulse">
                                <div className="text-xs text-neutral-400 w-[100px] shrink-0">...</div>
                                <div className="flex items-center gap-2 text-emerald-600">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500" />
                                    <span>Agent active</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Artifacts & Info */}
                <div className="col-span-12 lg:col-span-5 space-y-6">
                    {/* Artifacts */}
                    <Card>
                        <CardHeader className="pb-3 border-b border-neutral-100">
                            <CardTitle className="text-sm">Artifacts produced</CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3 p-0">
                            {task.artifacts && task.artifacts.length > 0 ? (
                                <div className="divide-y divide-neutral-100">
                                    {task.artifacts.map(art => (
                                        <div key={art.id} className="p-3 flex items-center justify-between hover:bg-neutral-50">
                                            <div className="flex items-center gap-3">
                                                {art.type === 'sql' || art.type === 'code' ? <Code className="w-4 h-4 text-blue-500" /> : <FileText className="w-4 h-4 text-neutral-500" />}
                                                <div>
                                                    <div className="text-sm font-medium text-neutral-900">{art.name}</div>
                                                    <div className="text-xs text-neutral-500">{art.type} • {art.size_bytes}B</div>
                                                </div>
                                            </div>
                                            <Link to="/tasks/$taskId/artifacts/$artifactId" params={{ taskId: task.id, artifactId: art.id }}>
                                                <Button variant="ghost" size="sm" className="h-7 text-xs">View</Button>
                                            </Link>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="p-4 text-sm text-neutral-500">No artifacts yet.</div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Safety Gates */}
                    <Card>
                        <CardHeader className="pb-3 border-b border-neutral-100">
                            <CardTitle className="text-sm">Safety Gates</CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3">
                            <div className="space-y-3">
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-neutral-600">Gate 1: Schema Validation</span>
                                    {task.gate_results?.gate_1 ? (
                                        <Badge variant="success" className="h-5 px-1.5"><CheckCircle2 className="w-3 h-3 mr-1" /> Pass</Badge>
                                    ) : (
                                        <Badge variant="secondary" className="h-5 px-1.5"><Circle className="w-3 h-3 mr-1" /> Pending</Badge>
                                    )}
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-neutral-600">Gate 2: Policy Check</span>
                                    {task.gate_results?.gate_2 ? (
                                        <Badge variant="success" className="h-5 px-1.5"><CheckCircle2 className="w-3 h-3 mr-1" /> Pass</Badge>
                                    ) : (
                                        <Badge variant="secondary" className="h-5 px-1.5"><Circle className="w-3 h-3 mr-1" /> Pending</Badge>
                                    )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Resources */}
                    <Card>
                        <CardHeader className="pb-3 border-b border-neutral-100">
                            <CardTitle className="text-sm">Resources</CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3">
                            <div className="space-y-4">
                                <div>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-neutral-600">Token Budget</span>
                                        <span className="text-neutral-900 font-medium">12.4k / 50k</span>
                                    </div>
                                    <div className="h-2 w-full bg-neutral-100 rounded-full overflow-hidden">
                                        <div className="h-full bg-primary-500 w-[25%]" />
                                    </div>
                                </div>

                                <div className="flex justify-between text-xs text-neutral-600">
                                    <div className="flex items-center gap-1"><Clock className="w-3 h-3" /> Duration: 12m</div>
                                    <div>Retries: 0</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </Grid>

            {/* Action Bar (Sticky) */}
            <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-200 p-4 z-10 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                <div className="max-w-[1440px] mx-auto px-8 flex justify-between items-center">
                    <Button variant="ghost" className="text-rose-600 hover:bg-rose-50 hover:text-rose-700" onClick={handleCancel} disabled={isCancelling}>
                        Cancel Task
                    </Button>
                    <div className="text-xs text-neutral-400">
                        Auto-refreshing every 5s • Last update: Just now
                    </div>
                </div>
            </div>
        </div>
    )
}
