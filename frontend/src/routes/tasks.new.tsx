import { createFileRoute, useNavigate, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { api } from '../api/client'
import { Button } from '../components/ui/Button'
import { Textarea } from '../components/ui/Textarea'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { Select } from '../components/ui/Select'
import { Badge } from '../components/ui/Badge'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { Grid } from '../components/layout/Grid'

export const Route = createFileRoute('/tasks/new')({
    component: TaskSubmissionPage,
})

function TaskSubmissionPage() {
    const navigate = useNavigate()
    const [description, setDescription] = useState("")
    const [environment, setEnvironment] = useState("SANDBOX")
    const [priority, setPriority] = useState("MEDIUM")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleSubmit = async () => {
        if (!description.trim()) return

        setIsSubmitting(true)
        setError(null)

        try {
            const task = await api.createTask({
                description,
                environment,
                priority
            })
            // Redirect to task detail
            navigate({ to: `/tasks/${task.id}` })
        } catch (e: any) {
            setError(e.message || "Failed to submit task")
            setIsSubmitting(false)
        }
    }

    return (
        <div className="space-y-6">
            {/* Breadcrumb / Header */}
            <div className="flex items-center gap-2 text-sm text-neutral-500">
                <Link to="/" className="hover:text-neutral-900">All Tasks</Link>
                <span>/</span>
                <span className="font-medium text-neutral-900">Submit New Task</span>
            </div>

            <Grid className="px-0 max-w-none" gap={8}> {/* Override px-8 from Grid default since we are inside main */}
                {/* Left Column: Input */}
                <div className="col-span-12 lg:col-span-7 space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Task Definition</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-neutral-700">Description</label>
                                <Textarea
                                    className="min-h-[200px] font-mono text-sm"
                                    placeholder="Describe your data engineering task in natural language..."
                                    value={description}
                                    onChange={e => setDescription(e.target.value)}
                                />
                                <p className="text-xs text-neutral-500">
                                    Be specific about table names, schemas, and desired outcomes.
                                </p>
                            </div>

                            <div className="grid grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-neutral-700">Environment</label>
                                    <SegmentedControl
                                        options={[
                                            { label: 'Sandbox', value: 'SANDBOX' },
                                            { label: 'Production', value: 'PRODUCTION' }
                                        ]}
                                        value={environment}
                                        onChange={setEnvironment}
                                        className="w-full"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-neutral-700">Priority</label>
                                    <Select value={priority} onChange={e => setPriority(e.target.value)}>
                                        <option value="LOW">Low</option>
                                        <option value="MEDIUM">Medium</option>
                                        <option value="HIGH">High</option>
                                        <option value="CRITICAL">Critical</option>
                                    </Select>
                                </div>
                            </div>

                            {environment === 'PRODUCTION' && (
                                <div className="bg-amber-50 border border-amber-200 rounded-md p-3 flex items-start gap-2">
                                    <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
                                    <div className="text-sm text-amber-900">
                                        <span className="font-medium">Production tasks require approval.</span>
                                        <br />
                                        Destructive operations and schema changes will be gated by INV-01.
                                    </div>
                                </div>
                            )}

                            {error && (
                                <div className="bg-rose-50 border border-rose-200 rounded-md p-3 text-sm text-rose-700">
                                    {error}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <div className="flex items-center justify-between">
                        <div className="text-sm text-neutral-500">
                            Est. Budget: ~2,500 tokens
                        </div>
                        <div className="flex gap-3">
                            <Button variant="ghost" onClick={() => navigate({ to: '/' })}>Cancel</Button>
                            <Button onClick={handleSubmit} isLoading={isSubmitting} disabled={!description.trim()}>
                                Submit Task
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Right Column: Governance */}
                <div className="col-span-12 lg:col-span-5 space-y-6">
                    <Card className="bg-neutral-50 border-neutral-200">
                        <CardHeader>
                            <CardTitle className="text-base">Governance Rules</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <p className="text-sm text-neutral-600">
                                Your task will be parsed, planned, and executed by an autonomous agent pool.
                                Safety gates are enforced at every step.
                            </p>

                            <div className="text-sm">
                                <h4 className="font-medium text-neutral-900 mb-2">Autonomy Matrix</h4>
                                <div className="rounded-md border border-neutral-200 overflow-hidden">
                                    <table className="w-full text-xs">
                                        <thead className="bg-neutral-100 border-b border-neutral-200">
                                            <tr>
                                                <th className="px-3 py-2 text-left font-medium">Env</th>
                                                <th className="px-3 py-2 text-left font-medium">Op</th>
                                                <th className="px-3 py-2 text-left font-medium">Approval</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-neutral-200 bg-white">
                                            <tr>
                                                <td className="px-3 py-2 text-neutral-500">SBOX</td>
                                                <td className="px-3 py-2">Read/Write</td>
                                                <td className="px-3 py-2 text-emerald-600">Auto</td>
                                            </tr>
                                            <tr>
                                                <td className="px-3 py-2 text-neutral-500">PROD</td>
                                                <td className="px-3 py-2">Read</td>
                                                <td className="px-3 py-2 text-emerald-600">Auto</td>
                                            </tr>
                                            <tr>
                                                <td className="px-3 py-2 text-neutral-500">PROD</td>
                                                <td className="px-3 py-2 font-medium">Write</td>
                                                <td className="px-3 py-2 text-amber-600 font-medium">Required</td>
                                            </tr>
                                            <tr>
                                                <td className="px-3 py-2 text-neutral-500">ANY</td>
                                                <td className="px-3 py-2 font-medium text-rose-600">Destructive</td>
                                                <td className="px-3 py-2 text-amber-600 font-medium">Required (INV-01)</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </Grid>
        </div>
    )
}
