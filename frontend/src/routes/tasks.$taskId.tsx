import { Outlet, createFileRoute } from '@tanstack/react-router'
import { api } from '../api/client'
import { Task } from '../api/types'

export const Route = createFileRoute('/tasks/$taskId')({
    component: TaskLayout,
    loader: async ({ params }) => {
        try {
            const task = await api.getTask(params.taskId)
            return { task }
        } catch (e) {
            console.error(e)
            // If error, likely 404, but for now we throw to trigger error boundary 
            // or return null and let component handle
            throw e
        }
    },
})

function TaskLayout() {
    return (
        <div>
            <Outlet />
        </div>
    )
}
