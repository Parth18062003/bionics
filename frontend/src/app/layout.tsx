'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import './globals.css';

const NAV_LINKS = [
  { href: '/', label: 'Dashboard' },
  { href: '/marketplace', label: 'Marketplace' },
  { href: '/tasks', label: 'Tasks' },
  { href: '/tasks/new', label: 'New Task' },
  { href: '/approvals', label: 'Approvals' },
];

function NavBar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <nav className="nav-bar">
      <div className="nav-inner">
        <Link href="/" className="nav-logo">
          <div className="nav-logo-icon">A</div>
          AADAP
        </Link>
        <div className="nav-links">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`nav-link ${isActive(href) ? 'nav-link-active' : ''}`}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <title>AADAP — Control Plane</title>
        <meta
          name="description"
          content="Autonomous AI Developer Agents Platform — Enterprise control plane for data engineering workflows."
        />
      </head>
      <body>
        <NavBar />
        <main>{children}</main>
      </body>
    </html>
  );
}
