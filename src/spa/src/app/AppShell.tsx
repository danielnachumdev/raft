import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { InboxBell } from "../features/inbox/InboxBell";
import { useRbac } from "../features/rbac";
import { versionChromeText } from "../shared/api/status";
import { MobileNav } from "./MobileNav";
import {
  ADD_SERVICE_NAV,
  anySettingsAllowed,
  firstSettingsPath,
  isNavActive,
  isSettingsPath,
  navAllowed,
  SETTINGS_NAV,
  TOPBAR_NAV,
} from "./navItems";
import { SettingsSubNav } from "./SettingsSubNav";
import { UserMenu } from "./UserMenu";
import { useRaftVersion } from "./useRaftVersion";
import "./AppShell.css";

/** Persistent top bar (brand, primary nav, tools) around every route. */
export function AppShell() {
  const { pathname } = useLocation();
  const { can } = useRbac();
  const nav = TOPBAR_NAV.filter((item) => navAllowed(item, can));
  const settingsHub = isSettingsPath(pathname);
  useEffect(() => {
    if (settingsHub) document.body.dataset.settingsHub = "";
    else delete document.body.dataset.settingsHub;
    return () => {
      delete document.body.dataset.settingsHub;
    };
  }, [settingsHub]);
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
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                id={item.id}
                end
                className={() =>
                  isNavActive(pathname, item)
                    ? "topbar-link is-active"
                    : "topbar-link"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <TopbarTools pathname={pathname} />
        </div>
        <SettingsSubNav />
      </header>
      <main className="page" id="main">
        <Outlet />
      </main>
    </>
  );
}

/** Add service CTA, version, Settings gear, account menu, and the mobile menu. */
function TopbarTools(props: { pathname: string }) {
  const version = useRaftVersion();
  const { can } = useRbac();
  const showSettings = anySettingsAllowed(can);
  const settingsTo = firstSettingsPath(can);
  const settingsActive = isSettingsPath(props.pathname);
  return (
    <div className="topbar-tools">
      <NavLink
        to={ADD_SERVICE_NAV.to}
        id={ADD_SERVICE_NAV.id}
        end
        className={() =>
          isNavActive(props.pathname, ADD_SERVICE_NAV)
            ? "btn btn-sm topbar-cta is-active"
            : "btn btn-sm topbar-cta"
        }
      >
        <span aria-hidden="true">+</span>
        {ADD_SERVICE_NAV.label}
      </NavLink>
      {version ? (
        version.url ? (
          <a
            className="topbar-version topbar-version--link"
            id="raft-version"
            href={version.url}
            target="_blank"
            rel="noreferrer"
            title={version.line}
          >
            v{versionChromeText(version)}
          </a>
        ) : (
          <span className="topbar-version" id="raft-version" title={version.line}>
            v{versionChromeText(version)}
          </span>
        )
      ) : null}
      <InboxBell />
      {showSettings ? (
        <NavLink
          to={settingsTo}
          id={SETTINGS_NAV.id}
          end={false}
          aria-label={SETTINGS_NAV.label}
          title={SETTINGS_NAV.label}
          className={() =>
            settingsActive
              ? "topbar-link topbar-link--icon is-active"
              : "topbar-link topbar-link--icon"
          }
        >
          <GearIcon />
        </NavLink>
      ) : null}
      <UserMenu />
      <MobileNav key={props.pathname} />
    </div>
  );
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
