import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/dev/components')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/dev/components"!</div>
}
