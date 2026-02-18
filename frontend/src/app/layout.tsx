'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import './globals.css';

const NAV_LINKS = [
  { href: '/dashboard',   label: 'Dashboard' },
  { href: '/marketplace', label: 'Marketplace' },
  { href: '/tasks',       label: 'Tasks' },
  { href: '/tasks/new',   label: 'New Task' },
  { href: '/approvals',   label: 'Approvals' },
];

/**
 * Determine whether a nav link should be highlighted as active.
 *
 * Rules:
 *  - '/tasks/new' is exact-matched (so it doesn't also activate '/tasks').
 *  - '/tasks' is active for '/tasks', '/tasks/[id]', but NOT '/tasks/new'.
 *  - All other top-level routes use startsWith so that child pages
 *    (e.g. '/approvals/[id]') correctly highlight the parent nav link.
 */
function isNavActive(href: string, pathname: string): boolean {
  if (href === '/tasks/new') return pathname === '/tasks/new';
  if (href === '/tasks') {
    return (
      pathname === '/tasks' ||
      (pathname.startsWith('/tasks/') && !pathname.startsWith('/tasks/new'))
    );
  }
  return pathname === href || pathname.startsWith(href + '/');
}

function NavBar() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  // Close mobile menu when Escape is pressed
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  return (
    <nav className="nav-bar" aria-label="Main navigation">
      <div className="nav-inner">
        {/* Logo */}
        <Link href="/" className="nav-logo" aria-label="AADAP home">
          <div className="nav-logo-icon" aria-hidden="true">A</div>
          AADAP
        </Link>

        {/* Desktop links */}
        <div className="nav-links" role="list">
          {NAV_LINKS.map(({ href, label }) => {
            const active = isNavActive(href, pathname);
            return (
              <Link
                key={href}
                href={href}
                role="listitem"
                className={`nav-link${active ? ' nav-link-active' : ''}`}
                aria-current={active ? 'page' : undefined}
              >
                {label}
              </Link>
            );
          })}
        </div>

        {/* Hamburger — visible only on mobile (≤680 px) */}
        <button
          className="nav-menu-toggle"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls="nav-mobile-menu"
          onClick={() => setMenuOpen((prev) => !prev)}
        >
          {/* Simple three-bar / cross icon via SVG */}
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            aria-hidden="true"
          >
            {menuOpen ? (
              <>
                <line x1="3" y1="3" x2="15" y2="15" />
                <line x1="15" y1="3" x2="3" y2="15" />
              </>
            ) : (
              <>
                <line x1="2" y1="5"  x2="16" y2="5"  />
                <line x1="2" y1="9"  x2="16" y2="9"  />
                <line x1="2" y1="13" x2="16" y2="13" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Mobile drawer */}
      <div
        id="nav-mobile-menu"
        className={`nav-mobile${menuOpen ? ' nav-mobile-open' : ''}`}
        aria-hidden={!menuOpen}
      >
        {NAV_LINKS.map(({ href, label }) => {
          const active = isNavActive(href, pathname);
          return (
            <Link
              key={href}
              href={href}
              className={`nav-link${active ? ' nav-link-active' : ''}`}
              aria-current={active ? 'page' : undefined}
              tabIndex={menuOpen ? 0 : -1}
            >
              {label}
            </Link>
          );
        })}
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
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta
          name="description"
          content="Autonomous AI Developer Agents Platform — Enterprise control plane for data engineering workflows."
        />
      </head>
      <body>
        {/* Skip-to-main for keyboard & screen-reader users */}
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>

        <NavBar />

        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
      </body>
    </html>
  );
}
