import { createFileRoute, useNavigate, Link } from '@tanstack/react-router'
import { api } from '../api/client'
import { Button } from '../components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Textarea } from '../components/ui/Textarea'
import { AlertTriangle, CheckCircle, XCircle, FileDiff, ShieldAlert, History } from 'lucide-react'
import { useState } from 'react'

export const Route = createFileRoute('/tasks/$taskId/review')({
    component: ApprovalPage,
    loader: async ({ params }) => {
        return { task: await api.getTask(params.taskId) }
    }
})

function ApprovalPage() {
    const { task } = Route.useLoaderData()
    const navigate = useNavigate()
    const [comment, setComment] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleAction = async (action: 'approve' | 'reject') => {
        setIsSubmitting(true)
        try {
            await api.updateTaskState(task.id, action, { comment })
            navigate({ to: '/tasks/$taskId', params: { taskId: task.id } })
        } catch (e) {
            alert(`Failed to ${action}`)
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="space-y-6 pb-24">
            {/* Alert Banner */}
            <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-md flex items-center justify-between shadow-sm">
                <div className="flex items-center gap-3">
                    <ShieldAlert className="h-6 w-6 text-amber-600" />
                    <div>
                        <p className="text-sm font-bold text-amber-900">Human Approval Required (INV-01)</p>
                        <p className="text-xs text-amber-700">Production Write Operation • Waiting 23 min</p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* Left Panel: Context */}
                <div className="col-span-12 lg:col-span-6 space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Task Context</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex justify-between items-start">
                                <div>
                                    <h3 className="text-lg font-mono font-bold">{task.id}</h3>
                                    <p className="text-sm text-neutral-600">{task.description}</p>
                                </div>
                                <Badge variant="outline" className="border-rose-200 bg-rose-50 text-rose-700">PROD</Badge>
                            </div>

                            <div className="bg-neutral-50 p-3 rounded-md border border-neutral-200 text-sm">
                                <div className="font-medium text-neutral-900 mb-2">Why is approval required?</div>
                                <ul className="list-disc list-inside space-y-1 text-neutral-600">
                                    <li>Production environment target</li>
                                    <li>Write operation detected (INSERT, ALTER)</li>
                                    <li>Risk Score: 0.82 (HIGH)</li>
                                </ul>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Execution Plan</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ol className="list-decimal list-inside space-y-2 text-sm text-neutral-700">
                                <li>Alter table <code className="bg-neutral-100 px-1 py-0.5 rounded">analytics.fact_sessions</code></li>
                                <li>Backfill 2.1M rows from stage</li>
                                <li>Update materialized views</li>
                                <li>Validate row counts</li>
                            </ol>
                        </CardContent>
                    </Card>
                </div>

                {/* Right Panel: Code & Audit */}
                <div className="col-span-12 lg:col-span-6 space-y-6">
                    <Card className="overflow-hidden">
                        <CardHeader className="bg-neutral-900 border-b border-neutral-800 py-3">
                            <div className="flex justify-between items-center text-white">
                                <CardTitle className="text-sm flex items-center gap-2"><FileDiff className="w-4 h-4" /> Code Preview</CardTitle>
                                <span className="text-xs text-neutral-400">scaling_policy.sql</span>
                            </div>
                        </CardHeader>
                        <div className="bg-[#1E1E2E] p-4 text-xs font-mono text-neutral-300 overflow-x-auto">
                            <pre>{`-- Scaling policy optimization
-- Generated by dev-agent-07

ALTER TABLE analytics.fact_sessions 
    ADD COLUMN processing_tier VARCHAR(20);

INSERT INTO analytics.fact_sessions
    SELECT * FROM stage.new_sessions;
`}</pre>
                        </div>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2"><History className="w-4 h-4" /> Audit Trail</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4 relative pl-4 border-l border-neutral-200">
                                {task.logs?.slice(0, 5).map((log, i) => (
                                    <div key={i} className="text-sm">
                                        <div className="absolute -left-1.5 w-3 h-3 rounded-full bg-neutral-200 border-2 border-white" />
                                        <div className="text-xs text-neutral-500">{new Date(log.timestamp).toLocaleTimeString()}</div>
                                        <div className="font-medium text-neutral-900">{log.message}</div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* Action Bar */}
            <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-200 p-4 z-20 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                <div className="max-w-[1440px] mx-auto px-8 flex flex-col md:flex-row gap-4 justify-between items-end md:items-center">
                    <div className="w-full md:w-1/2">
                        <Textarea
                            placeholder="Add a comment (required for rejection)..."
                            className="h-12 min-h-[48px] resize-none"
                            value={comment}
                            onChange={e => setComment(e.target.value)}
                        />
                    </div>
                    <div className="flex gap-3">
                        <Link to="/tasks/$taskId" params={{ taskId: task.id }}>
                            <Button variant="ghost">Cancel</Button>
                        </Link>
                        <Button
                            variant="destructive"
                            onClick={() => handleAction('reject')}
                            isLoading={isSubmitting}
                            className="bg-rose-100 text-rose-700 hover:bg-rose-200 border-rose-200"
                        >
                            <XCircle className="w-4 h-4 mr-2" /> Reject
                        </Button>
                        <Button
                            variant="primary"
                            onClick={() => handleAction('approve')}
                            isLoading={isSubmitting}
                            className="bg-emerald-600 hover:bg-emerald-700 border-emerald-600 text-white"
                        >
                            <CheckCircle className="w-4 h-4 mr-2" /> Approve (INV-01)
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}
