import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { NavLink, useLocation } from "react-router-dom";
import { LogoutButton } from "./LogoutButton";
import { matchesNavExtra, TOPBAR_NAV } from "./navItems";
import "./MobileNav.css";

/** Hamburger + panel with the same destinations as the desktop top-bar nav. */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState<CSSProperties>({});
  const { pathname } = useLocation();
  const menuId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const close = () => setOpen(false);

  useLayoutEffect(() => {
    if (!open) return;
    setPanelStyle(panelAnchor(buttonRef));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    document.body.dataset.mobileNavOpen = "true";
    const restore = previousFocus.current ?? buttonRef.current;
    panelRef.current?.focus();
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      delete document.body.dataset.mobileNavOpen;
      document.removeEventListener("keydown", onKey);
      restore?.focus();
    };
  }, [open]);

  return (
    <div className="mobile-nav">
      <button
        ref={buttonRef}
        type="button"
        className="mobile-nav-toggle"
        id="nav-menu-toggle"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <HamburgerIcon open={open} />
      </button>
      {open
        ? createPortal(
            <>
              <button
                type="button"
                className="mobile-nav-backdrop"
                aria-label="Close menu"
                tabIndex={-1}
                onClick={close}
              />
              <div
                ref={panelRef}
                id={menuId}
                className="mobile-nav-panel"
                role="dialog"
                aria-modal="true"
                aria-label="Primary"
                tabIndex={-1}
                style={panelStyle}
                onKeyDown={trapTab}
              >
                <nav className="mobile-nav-list" aria-label="Primary">
                  {TOPBAR_NAV.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      id={`mobile-${item.id}`}
                      end
                      className={({ isActive }) =>
                        isActive || matchesNavExtra(pathname, item)
                          ? "mobile-nav-link is-active"
                          : "mobile-nav-link"
                      }
                      onClick={close}
                    >
                      {item.label}
                    </NavLink>
                  ))}
                </nav>
                <div className="mobile-nav-footer">
                  <LogoutButton
                    className="mobile-nav-logout"
                    id="mobile-dashboard-logout"
                  />
                </div>
              </div>
            </>,
            document.body,
          )
        : null}
    </div>
  );
}

function panelAnchor(
  buttonRef: RefObject<HTMLButtonElement | null>,
): CSSProperties {
  const rect = buttonRef.current?.getBoundingClientRect();
  if (!rect) return { top: "3.25rem", right: "0.85rem" };
  return {
    top: `${Math.round(rect.bottom + 8)}px`,
    right: `${Math.round(window.innerWidth - rect.right)}px`,
  };
}

function HamburgerIcon(props: { open: boolean }) {
  return (
    <span className="mobile-nav-icon" aria-hidden="true">
      <span className={props.open ? "is-open" : undefined} />
      <span className={props.open ? "is-open" : undefined} />
      <span className={props.open ? "is-open" : undefined} />
    </span>
  );
}

function trapTab(event: KeyboardEvent<HTMLDivElement>) {
  if (event.key !== "Tab") return;
  const root = event.currentTarget;
  const focusable = root.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
  );
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
