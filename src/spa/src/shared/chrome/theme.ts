export type Theme = "light" | "dark";

const STORAGE_KEY = "raft-serve-theme";

/** Read a stored preference, or null if unset / invalid. */
export function readStoredTheme(): Theme | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === "light" || raw === "dark") return raw;
  } catch {
    /* private mode / blocked storage */
  }
  return null;
}

/** OS preference when nothing is stored. */
export function systemTheme(): Theme {
  if (typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/** Stored override, else prefers-color-scheme. */
export function resolveTheme(): Theme {
  return readStoredTheme() ?? systemTheme();
}

/** Apply theme to `<html>` so CSS `[data-theme]` tokens take effect. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

/** Persist and apply. */
export function setTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore quota / private mode */
  }
  applyTheme(theme);
}

/** Flip light ↔ dark and persist. */
export function toggleTheme(current: Theme): Theme {
  const next: Theme = current === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
