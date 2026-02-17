import { createFileRoute } from '@tanstack/react-router'
import { api } from '../api/client'
import { Task } from '../api/types'
import { TaskRow } from '../components/business/TaskRow'
import { FilterBar } from '../components/business/FilterBar'
import { Button } from '../components/ui/Button'
import { Plus } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { Loader2 } from 'lucide-react'

// Define search params type
type DashboardSearch = {
  page: number
  env?: string
  state?: string
}

export const Route = createFileRoute('/')({
  component: Dashboard,
  validateSearch: (search: Record<string, unknown>): DashboardSearch => {
    return {
      page: Number(search?.page ?? 1),
      env: (search?.env as string) || undefined,
      state: (search?.state as string) || undefined,
    }
  },
  loaderDeps: ({ search: { page, env, state } }) => ({ page, env, state }),
  loader: async ({ deps: { env, state } }) => {
    try {
      const tasks = await api.getTasks({ environment: env, state })
      return { tasks }
    } catch (e) {
      console.error("Failed to load tasks", e)
      // Return empty tasks on error to avoid crashing UI, or throw to error boundary
      // For now, empty array + valid "tasks" prop is safer for UI
      return { tasks: [] as Task[], error: String(e) }
    }
  }
})

function Dashboard() {
  const { tasks, error } = Route.useLoaderData()
  // const navigate = Route.useNavigate() 

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-neutral-900">Task Dashboard</h1>
        <Link to="/tasks/new">
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Submit New Task
          </Button>
        </Link>
      </div>

      <FilterBar />

      {error ? (
        <div className="rounded-md bg-rose-50 p-4 text-sm text-rose-700 border border-rose-200">
          Failed to load tasks: {error}. Is the backend running?
        </div>
      ) : null}

      <div className="space-y-3">
        {tasks.length === 0 && !error ? (
          <div className="text-center py-20 bg-neutral-50 rounded-lg border border-neutral-100">
            <h3 className="text-neutral-900 font-medium mb-1">No tasks found</h3>
            <p className="text-neutral-500 text-sm mb-4">Get started by submitting your first task.</p>
            <Link to="/tasks/new">
              <Button variant="secondary">Submit Task</Button>
            </Link>
          </div>
        ) : (
          tasks.map(task => (
            <TaskRow key={task.id} task={task} />
          ))
        )}
      </div>

      {/* Pagination Placeholder */}
      {tasks.length > 0 && (
        <div className="flex justify-end pt-4">
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" disabled>Previous</Button>
            <Button variant="ghost" size="sm" className="bg-neutral-100">1</Button>
            <Button variant="ghost" size="sm">2</Button>
            <Button variant="ghost" size="sm">3</Button>
            <Button variant="ghost" size="sm">Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
