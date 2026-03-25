// src/components/Header.jsx
//
// Frosted-glass navigation bar, fixed to the top of every page.
//
// NAV_LINKS — top-level links rendered directly in the bar.
// NAV_DROPDOWN — links grouped under a single "Demo" dropdown.
// Add entries to either array as new pages are introduced rather
// than editing the JSX directly.

import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/tailwind.css';

/* ── Top-level navigation links ──────────────────────────────────*/
const NAV_LINKS = [
  { label: 'Home', to: '/' },
];

/* ── Dropdown entries ─────────────────────────────────────────────
   These appear under the "Demo" dropdown toggle in the nav bar.
─────────────────────────────────────────────────────────────────── */
const NAV_DROPDOWN = [
  { label: 'Knowledge Graph Generation', to: '/knowledge-graph' },
  { label: 'GraphRAG',                   to: '/graphrag'        },
];

export default function Header() {
  const location = useLocation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close the dropdown when the user clicks outside of it.
  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close the dropdown when the route changes (user navigated).
  useEffect(() => {
    setDropdownOpen(false);
  }, [location.pathname]);

  // True when the current route belongs to one of the dropdown entries.
  const dropdownActive = NAV_DROPDOWN.some(({ to }) => location.pathname === to);

  return (
    <header
      className="
        fixed top-0 left-0 right-0 z-50
        glass-block
        px-8 py-3
        flex items-center justify-between
      "
    >
      {/* ── Brand ───────────────────────────────────────────────── */}
      <Link
        to="/"
        className="
          font-grotesk font-bold tracking-widest uppercase
          text-white text-lg
          hover:opacity-75 transition-opacity duration-200
        "
      >
        Taine Elliott — Master's Dissertation
      </Link>

      {/* ── Navigation ──────────────────────────────────────────── */}
      <nav className="flex items-center gap-6">

        {/* Top-level links */}
        {NAV_LINKS.map(({ label, to }) => {
          const isActive = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={`
                font-mono text-sm tracking-wider uppercase
                transition-all duration-200 border-b-2
                ${isActive
                  ? 'text-white border-white'
                  : 'text-white/70 border-transparent hover:text-white hover:border-white/50'
                }
              `}
            >
              {label}
            </Link>
          );
        })}

        {/* Demo dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className={`
              flex items-center gap-1
              font-mono text-sm tracking-wider uppercase
              transition-all duration-200 border-b-2
              ${dropdownActive
                ? 'text-white border-white'
                : 'text-white/70 border-transparent hover:text-white hover:border-white/50'
              }
            `}
          >
            Demo
            {/* Chevron icon — flips when open */}
            <svg
              className={`w-3 h-3 transition-transform duration-200 ${dropdownOpen ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown panel */}
          {dropdownOpen && (
            <div
              className="
                absolute right-0 mt-3
                glass-block rounded-sm
                py-1 min-w-[220px]
                flex flex-col
              "
            >
              {NAV_DROPDOWN.map(({ label, to }) => {
                const isActive = location.pathname === to;
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`
                      px-4 py-2
                      font-mono text-sm tracking-wide
                      transition-colors duration-150
                      ${isActive
                        ? 'text-white bg-white/10'
                        : 'text-white/70 hover:text-white hover:bg-white/10'
                      }
                    `}
                  >
                    {label}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

      </nav>
    </header>
  );
}
