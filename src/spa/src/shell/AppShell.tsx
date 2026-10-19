import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ThemeToggle } from "../chrome/ThemeToggle";
import { useRaftVersion } from "./useRaftVersion";
import "./AppShell.css";

type NavItem = {
  to: string;
  label: string;
  id: string;
  /** Extra path prefixes that keep this item highlighted. */
  alsoActive?: string[];
};

const NAV: NavItem[] = [
  { to: "/", label: "Status", id: "nav-status", alsoActive: ["/service/"] },
  {
    to: "/add-service",
    label: "Add service",
    id: "nav-add-service",
    alsoActive: ["/deploy"],
  },
  { to: "/events", label: "Events", id: "nav-events" },
  {
    to: "/settings",
    label: "Settings",
    id: "nav-settings",
    alsoActive: [
      "/settings/edge-access",
      "/settings/alerts",
      "/settings/notifications",
    ],
  },
  { to: "/settings/edge-access", label: "Firewall", id: "nav-edge-access" },
  { to: "/settings/alerts", label: "Alerts", id: "nav-alerts" },
  {
    to: "/settings/notifications",
    label: "Notifications",
    id: "nav-notifications",
  },
];

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
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                id={item.id}
                end
                className={({ isActive }) =>
                  isActive || matchesExtra(pathname, item)
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

function matchesExtra(pathname: string, item: NavItem): boolean {
  return (item.alsoActive ?? []).some((prefix) => pathname.startsWith(prefix));
}
