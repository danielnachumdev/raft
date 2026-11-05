export const TOAST_TYPES = ["good", "bad", "warning", "regular"] as const;

export type ToastType = (typeof TOAST_TYPES)[number];

export type ToastAction = {
  href: string;
  label: string;
  external?: boolean;
};

export type ToastRecord = {
  id: string;
  type: ToastType;
  message: string;
  durationMs: number;
  href?: string;
  linkLabel?: string;
  actions?: ToastAction[];
};

export type ToastContentOptions = {
  message: string;
  durationMs?: number;
  href?: string;
  linkLabel?: string;
  actions?: ToastAction[];
};

export type ToastShowOptions = ToastContentOptions & {
  type?: ToastType;
};

export const TOAST_DURATION_MS: Record<ToastType, number> = {
  good: 3500,
  regular: 4000,
  warning: 6500,
  bad: 8000,
};

export type ToastExtras = {
  durationMs?: number;
  href?: string;
  linkLabel?: string;
  actions?: ToastAction[];
};
