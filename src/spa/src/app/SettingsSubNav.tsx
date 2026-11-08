import { NavLink, useLocation } from "react-router-dom";
import { useRbac } from "../features/rbac";
import {
  isNavActive,
  isSettingsPath,
  navAllowed,
  SETTINGS_SECTIONS,
} from "./navItems";
import "./SettingsSubNav.css";

/** Secondary settings hub tabs under the top bar (General + dedicated pages). */
export function SettingsSubNav() {
  const { pathname } = useLocation();
  const { can } = useRbac();
  if (!isSettingsPath(pathname)) return null;
  const sections = SETTINGS_SECTIONS.filter((item) => navAllowed(item, can));
  if (sections.length === 0) return null;
  return (
    <div className="settings-subnav" id="settings-subnav">
      <div className="settings-subnav-inner">
        <nav className="settings-subnav-nav" aria-label="Settings pages">
          {sections.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              id={item.id}
              end
              className={() =>
                isNavActive(pathname, item)
                  ? "settings-subnav-link is-active"
                  : "settings-subnav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
