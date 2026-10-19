import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ThemeToggle } from "../chrome/ThemeToggle";
import { LogoutButton } from "./LogoutButton";
import { MobileNav } from "./MobileNav";
import { matchesNavExtra, TOPBAR_NAV } from "./navItems";
import { useRaftVersion } from "./useRaftVersion";
import "./AppShell.css";

/** Persistent top bar (brand, primary nav, theme) around every route. */
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
                className={({ isActive }) =>
                  isActive || matchesNavExtra(pathname, item)
                    ? "topbar-link is-active"
                    : "topbar-link"
                }
              >
                {item.label}
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
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="page" id="main">
        <Outlet />
      </main>
    </>
  );
}
