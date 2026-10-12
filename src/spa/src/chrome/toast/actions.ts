import type { ToastAction } from "./types.ts";

export function resolveToastActions(record: {
  href?: string;
  linkLabel?: string;
  actions?: ToastAction[];
}): ToastAction[] {
  if (record.actions && record.actions.length > 0) return record.actions;
  if (record.href && record.linkLabel) {
    return [{ href: record.href, label: record.linkLabel }];
  }
  return [];
}
