export type NavGroup = "monitor" | "configure";

export type NavItem = {
  to: string;
  label: string;
  id: string;
  /** Extra path prefixes that keep this item highlighted. */
  alsoActive?: string[];
  group?: NavGroup;
};

/** Primary top-bar destinations, in display order (desktop nav + mobile menu). */
export const TOPBAR_NAV: NavItem[] = [
  {
    to: "/",
    label: "Status",
    id: "nav-status",
    alsoActive: ["/service/"],
    group: "monitor",
  },
  { to: "/events", label: "Events", id: "nav-events", group: "monitor" },
  { to: "/settings/alerts", label: "Alerts", id: "nav-alerts", group: "configure" },
  {
    to: "/settings/notifications",
    label: "Notifications",
    id: "nav-notifications",
    group: "configure",
  },
  {
    to: "/settings/edge-access",
    label: "Firewall",
    id: "nav-edge-access",
    group: "configure",
  },
];

/** Right-side top-bar tools (Add service CTA, Settings gear). */
export const ADD_SERVICE_NAV: NavItem = {
  to: "/add-service",
  label: "Add service",
  id: "nav-add-service",
  alsoActive: ["/deploy"],
};

export const SETTINGS_NAV: NavItem = {
  to: "/settings",
  label: "Settings",
  id: "nav-settings",
};

export const NAV_GROUP_LABELS: Record<NavGroup, string> = {
  monitor: "Monitor",
  configure: "Configure",
};

/** Exact route match, or one of the item's ``alsoActive`` prefixes. */
export function isNavActive(pathname: string, item: NavItem): boolean {
  const path = trimTrailingSlash(pathname);
  if (path === trimTrailingSlash(item.to)) return true;
  return (item.alsoActive ?? []).some((prefix) => path.startsWith(prefix));
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
