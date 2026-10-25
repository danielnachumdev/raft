import type { NavItem } from "../shell/navItems";

/** Inbox destination (bell + page); not outbound notification channels. */
export const INBOX_NAV: NavItem = {
  to: "/inbox",
  label: "Inbox",
  id: "nav-inbox",
};
