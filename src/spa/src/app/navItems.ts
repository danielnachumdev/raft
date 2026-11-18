export type NavItem = {
  to: string;
  label: string;
  id: string;
  /** Extra path prefixes that keep this item highlighted. */
  alsoActive?: string[];
  /** RBAC permission required to show this nav entry. */
  permission?: string;
};

/** Primary top-bar destinations. */
export const TOPBAR_NAV: NavItem[] = [
  {
    to: "/",
    label: "Status",
    id: "nav-status",
    alsoActive: ["/service/"],
  },
  {
    to: "/events",
    label: "Events",
    id: "nav-events",
    permission: "events:read",
  },
];

/** Settings hub sections shown in the settings sub-header. */
export const SETTINGS_SECTIONS: NavItem[] = [
  {
    to: "/settings",
    label: "General",
    id: "nav-settings-general",
    permission: "settings:read",
  },
  {
    to: "/settings/alerts",
    label: "Alerts",
    id: "nav-alerts",
    permission: "alerts:read",
  },
  {
    to: "/settings/notifications",
    label: "Notifications",
    id: "nav-notifications",
    permission: "notifications:read",
  },
  {
    to: "/settings/edge-access",
    label: "Firewall",
    id: "nav-edge-access",
    permission: "firewall:read",
  },
  {
    to: "/settings/rbac",
    label: "RBAC",
    id: "nav-rbac",
    permission: "rbac:read",
  },
];

/** Right-side top-bar tools (Add service CTA). */
export const ADD_SERVICE_NAV: NavItem = {
  to: "/add-service",
  label: "Add service",
  id: "nav-add-service",
  alsoActive: ["/deploy"],
};

/** Gear entry — highlighted on every ``/settings*`` route. */
export const SETTINGS_NAV: NavItem = {
  to: "/settings",
  label: "Settings",
  id: "nav-settings",
  alsoActive: ["/settings/"],
};

/** Exact route match, or one of the item's ``alsoActive`` prefixes. */
export function isNavActive(pathname: string, item: NavItem): boolean {
  const path = trimTrailingSlash(pathname);
  if (path === trimTrailingSlash(item.to)) return true;
  return (item.alsoActive ?? []).some((prefix) => path.startsWith(prefix));
}

/** True for host settings and every settings hub section. */
export function isSettingsPath(pathname: string): boolean {
  const path = trimTrailingSlash(pathname);
  return path === "/settings" || path.startsWith("/settings/");
}

/** Items without a ``permission`` are always shown. */
export function navAllowed(
  item: NavItem,
  can: (permission: string) => boolean,
): boolean {
  return !item.permission || can(item.permission);
}

/** First settings section the operator can open (gear target). */
export function firstSettingsPath(
  can: (permission: string) => boolean,
): string {
  return SETTINGS_SECTIONS.find((item) => navAllowed(item, can))?.to ?? "/settings";
}

/** True when at least one settings hub section is visible. */
export function anySettingsAllowed(
  can: (permission: string) => boolean,
): boolean {
  return SETTINGS_SECTIONS.some((item) => navAllowed(item, can));
}

function trimTrailingSlash(path: string): string {
  return path.length > 1 && path.endsWith("/") ? path.slice(0, -1) : path;
}
