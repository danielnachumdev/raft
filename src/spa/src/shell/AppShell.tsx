import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { LogoutButton } from "./LogoutButton";
import { MobileNav } from "./MobileNav";
import { matchesNavExtra, TOPBAR_NAV } from "./navItems";
import { useRaftVersion } from "./useRaftVersion";
import "./AppShell.css";

/** Persistent top bar (brand, primary nav, tools) around every route. */
export function AppShell() {
  const { pathname } = useLocation();
  const version = useRaftVersion();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link className="topbar-brand" to="/" aria-label="raft home">
            raft
          </Link>
          <nav className="topbar-nav" aria-label="Primary">
            {TOPBAR_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                id={item.id}
                end
                aria-label={item.icon ? item.label : undefined}
                title={item.icon ? item.label : undefined}
                className={({ isActive }) =>
                  linkClass(
                    isActive || matchesNavExtra(pathname, item),
                    Boolean(item.icon),
                  )
                }
              >
                {item.icon === "gear" ? <GearIcon /> : item.label}
              </NavLink>
            ))}
          </nav>
          <div className="topbar-tools">
            {version ? (
              <span
                className="topbar-version"
                id="raft-version"
                title={version.line}
              >
                v{version.package}
              </span>
            ) : null}
            <LogoutButton className="topbar-logout-desktop" />
            <MobileNav key={pathname} />
          </div>
        </div>
      </header>
      <main className="page" id="main">
        <Outlet />
      </main>
    </>
  );
}

function linkClass(active: boolean, icon: boolean): string {
  const base = icon ? "topbar-link topbar-link--icon" : "topbar-link";
  return active ? `${base} is-active` : base;
}

/** Cog mark for the Settings nav control (decorative; label via aria-label). */
function GearIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.6.9 1.01 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  );
}
