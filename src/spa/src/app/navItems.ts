export type NavGroup = "monitor" | "settings";

export type NavItem = {
  to: string;
  label: string;
  id: string;
  /** Extra path prefixes that keep this item highlighted. */
  alsoActive?: string[];
  group?: NavGroup;
  /** RBAC permission required to show this nav entry. */
  permission?: string;
};

/** Primary top-bar destinations (desktop + mobile monitor group). */
export const TOPBAR_NAV: NavItem[] = [
  {
    to: "/",
    label: "Status",
    id: "nav-status",
    alsoActive: ["/service/"],
    group: "monitor",
  },
  {
    to: "/events",
    label: "Events",
    id: "nav-events",
    group: "monitor",
    permission: "events:read",
  },
];

/** Settings hub sections shown in the settings sub-header (and mobile Settings group). */
export const SETTINGS_SECTIONS: NavItem[] = [
  {
    to: "/settings",
    label: "General",
    id: "nav-settings-general",
    group: "settings",
    permission: "settings:read",
  },
  {
    to: "/settings/alerts",
    label: "Alerts",
    id: "nav-alerts",
    group: "settings",
    permission: "alerts:read",
  },
  {
    to: "/settings/notifications",
    label: "Notifications",
    id: "nav-notifications",
    group: "settings",
    permission: "notifications:read",
  },
  {
    to: "/settings/edge-access",
    label: "Firewall",
    id: "nav-edge-access",
    group: "settings",
    permission: "firewall:read",
  },
  {
    to: "/settings/rbac",
    label: "RBAC",
    id: "nav-rbac",
    group: "settings",
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

export const NAV_GROUP_LABELS: Record<NavGroup, string> = {
  monitor: "Monitor",
  settings: "Settings",
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

/** Group consecutive items for the mobile menu headings. */
export function groupNav(items: NavItem[]): { group: NavGroup; items: NavItem[] }[] {
  const out: { group: NavGroup; items: NavItem[] }[] = [];
  for (const item of items) {
    const group = item.group ?? "monitor";
    const last = out[out.length - 1];
    if (last && last.group === group) last.items.push(item);
    else out.push({ group, items: [item] });
  }
  return out;
}

function trimTrailingSlash(path: string): string {
  return path.length > 1 && path.endsWith("/") ? path.slice(0, -1) : path;
}
