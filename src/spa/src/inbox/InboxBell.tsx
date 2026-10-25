import { useCallback, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { formatInboxBadge } from "./badgeFormat";
import { fetchInboxSummary } from "./inboxApi";
import { INBOX_NAV } from "./inboxNav";
import { isNavActive } from "../shell/navItems";
import "./InboxBell.css";

const POLL_MS = 15_000;

/** Topbar bell with unread badge; opens the Inbox page. */
export function InboxBell() {
  const { pathname } = useLocation();
  const [unread, setUnread] = useState(0);
  const [badge, setBadge] = useState<string | null>(null);
  const active = isNavActive(pathname, INBOX_NAV);

  const refresh = useCallback(async () => {
    try {
      const summary = await fetchInboxSummary();
      setUnread(summary.unreadCount);
      setBadge(summary.badge ?? formatInboxBadge(summary.unreadCount));
    } catch {
      /* keep last known badge on transient poll errors */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, pathname]);

  useEffect(() => {
    if (document.visibilityState === "hidden") return;
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    const onVis = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [refresh]);

  const label =
    unread > 0
      ? `Inbox, ${unread > 99 ? "more than 99" : unread} unread`
      : "Inbox";

  return (
    <NavLink
      to={INBOX_NAV.to}
      id={INBOX_NAV.id}
      end
      aria-label={label}
      title={INBOX_NAV.label}
      className={() =>
        active
          ? "topbar-link topbar-link--icon inbox-bell is-active"
          : "topbar-link topbar-link--icon inbox-bell"
      }
    >
      <BellIcon />
      {badge ? (
        <span className="inbox-bell-badge" aria-live="polite" aria-atomic="true">
          {badge}
        </span>
      ) : null}
    </NavLink>
  );
}

function BellIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M6.2 9.4a5.8 5.8 0 0 1 11.6 0c0 4.2 1.4 5.6 1.4 5.6H4.8s1.4-1.4 1.4-5.6Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path
        d="M10 18.2a2 2 0 0 0 4 0"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}
