import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { useRbac } from "../features/rbac";
import { LogoutButton } from "./LogoutButton";
import { useDashboardSession } from "./useDashboardSession";
import "./UserMenu.css";

/** Account control: identity + logout tucked under a user icon. */
export function UserMenu() {
  const { rbac } = useRbac();
  const identity = rbac?.identity?.trim() || "";
  const logoutHint = useDashboardSession();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const close = useCallback(() => setOpen(false), []);

  useDismiss(open, rootRef, close);

  if (!identity && !logoutHint) return null;

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className={
          open
            ? "topbar-link topbar-link--icon user-menu-trigger is-active"
            : "topbar-link topbar-link--icon user-menu-trigger"
        }
        id="nav-user-menu"
        aria-label="Account"
        title="Account"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        <UserIcon />
      </button>
      {open ? (
        <div className="user-menu-pop" role="menu" id={menuId}>
          {identity ? (
            <p
              className="user-menu-identity"
              id="dashboard-identity"
              title={identity}
            >
              {identity}
            </p>
          ) : null}
          {logoutHint ? (
            <LogoutButton
              className="user-menu-logout"
              id="dashboard-logout"
              hint={logoutHint}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function useDismiss(
  open: boolean,
  rootRef: { current: HTMLDivElement | null },
  close: () => void,
): void {
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, rootRef, close]);
}

function UserIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      aria-hidden="true"
    >
      {/* Same optical weight/box as GearIcon / BellIcon (18×18, stroke 1.75). */}
      <circle
        cx="12"
        cy="7.5"
        r="3.75"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <path
        d="M4.75 20.25c1.55-3.6 4.05-5.25 7.25-5.25s5.7 1.65 7.25 5.25"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
