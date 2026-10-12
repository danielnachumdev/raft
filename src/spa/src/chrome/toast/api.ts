import { clear, dismiss, enqueue } from "./store.ts";
import type {
  ToastContentOptions,
  ToastExtras,
  ToastShowOptions,
  ToastType,
} from "./types.ts";

function extrasFromContent(content: ToastContentOptions): ToastExtras {
  return {
    durationMs: content.durationMs,
    href: content.href,
    linkLabel: content.linkLabel,
    actions: content.actions,
  };
}

function show(message: string, type?: ToastType): string;
function show(options: ToastShowOptions): string;
function show(
  messageOrOptions: string | ToastShowOptions,
  type: ToastType = "regular",
): string {
  if (typeof messageOrOptions === "string") {
    return enqueue(type, messageOrOptions);
  }
  return enqueue(
    messageOrOptions.type ?? "regular",
    messageOrOptions.message,
    extrasFromContent(messageOrOptions),
  );
}

function typedToast(
  type: ToastType,
  messageOrOptions: string | ToastContentOptions,
  durationMs?: number,
): string {
  if (typeof messageOrOptions === "string") {
    return enqueue(type, messageOrOptions, { durationMs });
  }
  return enqueue(type, messageOrOptions.message, {
    durationMs: messageOrOptions.durationMs ?? durationMs,
    href: messageOrOptions.href,
    linkLabel: messageOrOptions.linkLabel,
    actions: messageOrOptions.actions,
  });
}

function good(message: string, durationMs?: number): string;
function good(options: ToastContentOptions): string;
function good(
  messageOrOptions: string | ToastContentOptions,
  durationMs?: number,
): string {
  return typedToast("good", messageOrOptions, durationMs);
}

function bad(message: string, durationMs?: number): string;
function bad(options: ToastContentOptions): string;
function bad(
  messageOrOptions: string | ToastContentOptions,
  durationMs?: number,
): string {
  return typedToast("bad", messageOrOptions, durationMs);
}

function warning(message: string, durationMs?: number): string;
function warning(options: ToastContentOptions): string;
function warning(
  messageOrOptions: string | ToastContentOptions,
  durationMs?: number,
): string {
  return typedToast("warning", messageOrOptions, durationMs);
}

function regular(message: string, durationMs?: number): string;
function regular(options: ToastContentOptions): string;
function regular(
  messageOrOptions: string | ToastContentOptions,
  durationMs?: number,
): string {
  return typedToast("regular", messageOrOptions, durationMs);
}

export const toast = {
  show,
  good,
  bad,
  warning,
  regular,
  dismiss,
  clear,
};
