import { createFileRoute } from '@tanstack/react-router'
import { api } from '../api/client'
import { AgentStatusBadge } from '../components/business/AgentStatusBadge'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { RefreshCw, CheckCircle2, AlertTriangle, Server, Activity, Database, HardDrive } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Link } from '@tanstack/react-router'

export const Route = createFileRoute('/health')({
    component: SystemHealthPage,
    loader: async () => {
        try {
            const health = await api.getHealth()
            return { health }
        } catch {
            // Fallback mock data if API fails to prevent white screen during dev
            return {
                health: {
                    services: { api: false, orchestrator: false, database: false, redis: false },
                    agents: [],
                    invariants: [],
                    events: []
                }
            }
        }
    }
})

function SystemHealthPage() {
    const { health } = Route.useLoaderData()
    const services = [
        { name: 'API Gateway', status: health.services.api, icon: Server },
        { name: 'Orchestrator', status: health.services.orchestrator, icon: Activity },
        { name: 'PostgreSQL', status: health.services.database, icon: Database },
        { name: 'Redis', status: health.services.redis, icon: HardDrive },
    ]

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-neutral-900">System Health</h1>
                    <p className="text-sm text-neutral-500">Real-time infrastructure and governance monitoring</p>
                </div>
                <Button variant="outline"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
            </div>

            {/* Service Status Strip */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {services.map(s => (
                    <Card key={s.name} className="flex items-center p-4 gap-4 border-l-4 border-l-transparent data-[status=true]:border-l-emerald-500 data-[status=false]:border-l-rose-500" data-status={s.status}>
                        <div className={`p-2 rounded-lg ${s.status ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'}`}>
                            <s.icon className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="font-medium text-neutral-900">{s.name}</div>
                            <div className={`text-xs ${s.status ? 'text-emerald-600' : 'text-rose-600'}`}>
                                {s.status ? 'Healthy' : 'Unhealthy'}
                            </div>
                        </div>
                    </Card>
                ))}
            </div>

            {/* Agent Pool */}
            <Card>
                <CardHeader>
                    <CardTitle>Agent Pool Status</CardTitle>
                </CardHeader>
                <div className="border-t border-neutral-100">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-neutral-50 text-neutral-500 font-medium">
                            <tr>
                                <th className="px-6 py-3">Agent ID</th>
                                <th className="px-6 py-3">Type</th>
                                <th className="px-6 py-3">Status</th>
                                <th className="px-6 py-3">Current Task</th>
                                <th className="px-6 py-3">Uptime</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-100">
                            {health.agents.length > 0 ? health.agents.map(agent => (
                                <tr key={agent.id} className="hover:bg-neutral-50/50">
                                    <td className="px-6 py-4 font-mono text-neutral-900">{agent.id}</td>
                                    <td className="px-6 py-4">{agent.type}</td>
                                    <td className="px-6 py-4">
                                        <AgentStatusBadge status={agent.status} />
                                    </td>
                                    <td className="px-6 py-4 font-mono text-neutral-500">
                                        {agent.current_task_id ? (
                                            <Link to="/tasks/$taskId" params={{ taskId: agent.current_task_id }} className="text-primary-600 hover:underline">
                                                {agent.current_task_id}
                                            </Link>
                                        ) : '—'}
                                    </td>
                                    <td className="px-6 py-4 text-neutral-500">{(agent.uptime_seconds / 3600).toFixed(1)}h</td>
                                </tr>
                            )) : (
                                <tr>
                                    <td colSpan={5} className="px-6 py-8 text-center text-neutral-500 italic">No agents connected to the pool.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </Card>

            {/* Governance Log */}
            <Card>
                <CardHeader>
                    <CardTitle>Invariant Enforcement Log</CardTitle>
                </CardHeader>
                <div className="p-4 bg-neutral-900 font-mono text-xs text-neutral-300 h-64 overflow-y-auto rounded-b-lg">
                    {health.events.length > 0 ? health.events.map((e, i) => (
                        <div key={i} className="mb-1">
                            <span className="text-neutral-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
                            <span className={`mx-2 font-bold ${e.level === 'ERROR' ? 'text-rose-500' : e.level === 'WARN' ? 'text-amber-500' : 'text-emerald-500'}`}>
                                [{e.level}]
                            </span>
                            <span>{e.message}</span>
                        </div>
                    )) : (
                        <div className="text-neutral-500 italic">No system events logged.</div>
                    )}
                </div>
            </Card>
        </div>
    )
}
