import { useState } from "react";
import {
  resolveTheme,
  toggleTheme,
  type Theme,
} from "./theme";
import "./ThemeToggle.css";

/** Sun/moon switch in the page header; preference survives reload. */
export function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>(() => resolveTheme());
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className={isDark ? "theme-toggle is-dark" : "theme-toggle"}
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
      onClick={() => setThemeState((t) => toggleTheme(t))}
    >
      <span className="theme-toggle__icon theme-toggle__sun" aria-hidden="true">
        <SunIcon />
      </span>
      <span className="theme-toggle__track" aria-hidden="true">
        <span className="theme-toggle__thumb" />
      </span>
      <span className="theme-toggle__icon theme-toggle__moon" aria-hidden="true">
        <MoonIcon />
      </span>
    </button>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M12 2.5v2.25M12 19.25V21.5M2.5 12h2.25M19.25 12H21.5M5.05 5.05l1.6 1.6M17.35 17.35l1.6 1.6M18.95 5.05l-1.6 1.6M6.65 17.35l-1.6 1.6"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
      <path
        d="M18.5 14.2A7.25 7.25 0 0 1 9.8 5.5 7.5 7.5 0 1 0 18.5 14.2Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  );
}
