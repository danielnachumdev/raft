import {
  SEND_TEST_API_AVAILABLE,
  SECRET_MASK,
  type NotificationChannelSettings,
  type NotificationStrategyInfo,
} from "./notificationsApi.ts";

/** True when the strategy catalog has no registered type ids. */
export function isEmptyStrategyCatalog(
  strategies: NotificationStrategyInfo[],
): boolean {
  return strategies.length === 0;
}

/** Type ids operators may pick in the form (catalog only — never invent). */
export function strategyTypeIds(
  strategies: NotificationStrategyInfo[],
): string[] {
  return strategies.map((item) => item.type_id);
}

/** Pretty-print opaque settings for the JSON editor (redacted values as-is). */
export function formatSettingsJson(
  settings: NotificationChannelSettings,
): string {
  return JSON.stringify(settings ?? {}, null, 2);
}

/** Parse settings JSON; empty / whitespace → `{}`. */
export function parseSettingsJson(
  text: string,
): NotificationChannelSettings {
  const trimmed = text.trim();
  if (!trimmed) return {};
  const parsed: unknown = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Settings must be a JSON object");
  }
  return parsed as NotificationChannelSettings;
}

/**
 * Send test is only offered when the API exists and the channel type is
 * registered. Today the API is absent → always false.
 */
export function canSendTest(
  strategies: NotificationStrategyInfo[],
  typeId: string,
): boolean {
  if (!SEND_TEST_API_AVAILABLE) return false;
  if (!typeId.trim()) return false;
  return strategyTypeIds(strategies).includes(typeId);
}

/** CTA when Send test is unavailable. */
export function sendTestDisabledReason(
  strategies: NotificationStrategyInfo[],
  typeId: string,
): string {
  if (!SEND_TEST_API_AVAILABLE) {
    return "Send test is not available yet.";
  }
  if (isEmptyStrategyCatalog(strategies)) {
    return "No notification strategies are registered.";
  }
  if (!strategyTypeIds(strategies).includes(typeId)) {
    return "Channel type is not in the strategy catalog.";
  }
  return "Send test is not available.";
}

/** Whether a settings value is the server redaction mask. */
export function isSecretMask(value: unknown): boolean {
  return value === SECRET_MASK;
}
