import {
  SEND_TEST_API_AVAILABLE,
  SECRET_MASK,
  type NotificationChannelSettings,
  type NotificationStrategyField,
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

/** Human label for a catalog type, falling back to the type id. */
export function strategyLabel(
  strategies: NotificationStrategyInfo[],
  typeId: string,
): string {
  const found = strategies.find((item) => item.type_id === typeId);
  const label = found?.label?.trim();
  return label || typeId;
}

/** Declared settings fields for a type, or empty when the catalog omits them. */
export function strategyFields(
  strategies: NotificationStrategyInfo[],
  typeId: string,
): NotificationStrategyField[] {
  const found = strategies.find((item) => item.type_id === typeId);
  return Array.isArray(found?.fields) ? found.fields : [];
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

/** Coerce a form string into a JSON-friendly settings value for ``kind``. */
export function coerceFieldValue(
  kind: string,
  raw: string,
): unknown {
  if (kind === "number") {
    const trimmed = raw.trim();
    if (!trimmed) return undefined;
    const num = Number(trimmed);
    if (Number.isNaN(num)) throw new Error("Timeout / number fields must be numeric");
    return num;
  }
  if (kind === "checkbox") return raw === "true";
  return raw;
}

/** Build a settings object from typed form state (skip empty optional keys). */
export function settingsFromFieldState(
  fields: NotificationStrategyField[],
  values: Record<string, string>,
): NotificationChannelSettings {
  const out: NotificationChannelSettings = {};
  for (const field of fields) {
    const raw = values[field.key] ?? "";
    if (field.kind === "checkbox") {
      out[field.key] = values[field.key] === "true";
      continue;
    }
    if (!raw.trim() && !field.required) continue;
    const coerced = coerceFieldValue(field.kind, raw);
    if (coerced !== undefined) out[field.key] = coerced;
  }
  return out;
}

/** Seed form state from an existing (possibly redacted) settings object. */
export function fieldStateFromSettings(
  fields: NotificationStrategyField[],
  settings: NotificationChannelSettings,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields) {
    out[field.key] = stringFromSetting(field.kind, settings[field.key]);
  }
  return out;
}

function stringFromSetting(kind: string, value: unknown): string {
  if (value === undefined || value === null) {
    return kind === "checkbox" ? "false" : "";
  }
  if (kind === "checkbox") {
    return value === true || value === "true" ? "true" : "false";
  }
  return String(value);
}
