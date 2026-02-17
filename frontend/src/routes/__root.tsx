import { Outlet, createRootRoute } from '@tanstack/react-router'
// import { Meta, Scripts } from '@tanstack/react-start'
import type { ReactNode } from 'react'
import { Link, useLocation } from '@tanstack/react-router'
import { Badge } from '../components/ui/Badge'
import { Bell, Search, User } from 'lucide-react'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import "../styles.css" // Ensure global styles are imported

function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  return (
    <RootDocument>
      <div className="min-h-screen bg-white font-sans text-neutral-900">
        <TopBar />
        <TabNav />
        <main className="mx-auto w-full max-w-[1440px] px-8 py-6">
          <Outlet />
        </main>
      </div>
    </RootDocument>
  )
}

function RootDocument({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* <Meta /> */}
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>AADAP Control Plane</title>
      </head>
      <body>
        {children}
        {/* <Scripts /> */}
      </body>
    </html>
  )
}

function TopBar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-neutral-200 bg-white px-8">
      <div className="flex items-center gap-2">
        {/* Logo Placeholder */}
        <div className="h-6 w-6 rounded-full bg-primary-600" />
        <span className="text-base font-semibold text-neutral-900">AADAP</span>
      </div>

      <div className="relative w-[360px]">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-neutral-400" />
        <input
          type="text"
          placeholder="Search tasks, agents, artifacts…"
          className="h-9 w-full rounded-md bg-neutral-50 pl-9 pr-4 text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <div className="absolute right-2 top-2 rounded border border-neutral-200 px-1.5 py-0.5 text-[10px] text-neutral-400">
          ⌘K
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button className="relative text-neutral-500 hover:text-neutral-700">
          <Bell className="h-5 w-5" />
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-rose-600 ring-2 ring-white" />
        </button>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-xs font-medium text-primary-700">
            JC
          </div>
          <div className="hidden flex-col md:flex">
            <span className="text-xs font-medium text-neutral-900">Julie Chen</span>
            <span className="text-[10px] text-neutral-500">Lead Engineer</span>
          </div>
        </div>
      </div>
    </header>
  )
}

function TabNav() {
  const { pathname } = useLocation()

  // Simple helper for active state
  // Exact match for dashboard, prefix match for others
  const isActive = (path: string) => {
    if (path === '/') return pathname === '/'
    return pathname.startsWith(path)
  }

  const tabs = [
    { label: 'All Tasks', path: '/', count: null },
    { label: 'Pending Approval', path: '/approvals', count: 4, alert: true }, // Logic for /approvals filter
    { label: 'Failed', path: '/failed', count: null },
    { label: 'Completed', path: '/completed', count: null },
    { label: 'System Health', path: '/health', count: null },
  ]

  return (
    <nav className="flex h-[44px] items-center space-x-8 border-b border-neutral-200 bg-neutral-50 px-8">
      {tabs.map((tab) => (
        <Link
          key={tab.label}
          to={tab.path}
          className={cn(
            "flex h-full items-center gap-2 border-b-2 px-1 text-sm font-medium transition-colors hover:text-neutral-900",
            isActive(tab.path)
              ? "border-primary-500 text-neutral-900"
              : "border-transparent text-neutral-500"
          )}
        >
          {tab.label}
          {tab.count !== null && (
            <span className={cn(
              "text-xs",
              tab.alert ? "text-amber-600 font-bold" : "text-neutral-400"
            )}>
              ({tab.count})
            </span>
          )}
        </Link>
      ))}
    </nav>
  )
}
