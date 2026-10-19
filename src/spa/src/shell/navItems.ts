export type NavItem = {
  to: string;
  label: string;
  id: string;
  /** Extra path prefixes that keep this item highlighted. */
  alsoActive?: string[];
  /** When set, desktop nav renders an icon button instead of the text label. */
  icon?: "gear";
};

/** Primary top-bar destinations (desktop nav + mobile menu). */
export const TOPBAR_NAV: NavItem[] = [
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
    icon: "gear",
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

export function matchesNavExtra(pathname: string, item: NavItem): boolean {
  return (item.alsoActive ?? []).some((prefix) => pathname.startsWith(prefix));
}
