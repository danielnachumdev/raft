/** Copy for purge start / finish toasts (PII-free; reclaim is Docker summary). */

export function purgeStartedMessage(): string {
  return "Purge started — removing unused images in the background.";
}

export function purgeSuccessMessage(human: string): string {
  if (!human || human === "0B" || human === "-") {
    return "Purge finished — nothing to reclaim (0B).";
  }
  return `Purge finished — reclaimed ${human}.`;
}

export function purgeFailureMessage(detail: string): string {
  return `Purge failed: ${detail}`;
}
