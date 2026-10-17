import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canSendTest,
  coerceFieldValue,
  fieldStateFromSettings,
  formatSettingsJson,
  isEmptyStrategyCatalog,
  isSecretMask,
  parseSettingsJson,
  sendTestDisabledReason,
  settingsFromFieldState,
  strategyFields,
  strategyLabel,
  strategyTypeIds,
} from "../../src/notifications/notificationsHelpers.ts";
import { SECRET_MASK } from "../../src/notifications/notificationsApi.ts";

const whatsapp = {
  type_id: "whatsapp",
  label: "WhatsApp (GREEN-API)",
  fields: [
    {
      key: "apiUrl",
      label: "API URL",
      kind: "url",
      required: true,
    },
    {
      key: "apiTokenInstance",
      label: "API token",
      kind: "secret",
      required: true,
    },
    {
      key: "timeoutSeconds",
      label: "Timeout",
      kind: "number",
      required: false,
    },
    {
      key: "allowInsecureHttp",
      label: "Allow HTTP",
      kind: "checkbox",
      required: false,
    },
  ],
};

describe("isEmptyStrategyCatalog", () => {
  it("is true for an empty strategies list", () => {
    assert.equal(isEmptyStrategyCatalog([]), true);
  });

  it("is false when a type is registered", () => {
    assert.equal(isEmptyStrategyCatalog([{ type_id: "webhook" }]), false);
  });
});

describe("strategyTypeIds / label / fields", () => {
  it("maps catalog entries without inventing types", () => {
    assert.deepEqual(
      strategyTypeIds([{ type_id: "webhook" }, { type_id: "email" }]),
      ["webhook", "email"],
    );
  });

  it("uses catalog labels and fields when present", () => {
    assert.equal(strategyLabel([whatsapp], "whatsapp"), "WhatsApp (GREEN-API)");
    assert.equal(strategyLabel([{ type_id: "x" }], "x"), "x");
    assert.equal(strategyFields([whatsapp], "whatsapp").length, 4);
    assert.deepEqual(strategyFields([{ type_id: "x" }], "x"), []);
  });
});

describe("settings JSON", () => {
  it("formats and parses an opaque object", () => {
    const settings = { url: "https://hooks.example.invalid/x", token: SECRET_MASK };
    const text = formatSettingsJson(settings);
    assert.match(text, /hooks\.example\.invalid/);
    assert.deepEqual(parseSettingsJson(text), settings);
  });

  it("treats blank settings text as empty object", () => {
    assert.deepEqual(parseSettingsJson("  "), {});
  });

  it("rejects non-object JSON", () => {
    assert.throws(() => parseSettingsJson("[]"), /JSON object/);
  });
});

describe("typed field state", () => {
  it("builds settings from form values and seeds from redacted settings", () => {
    const settings = settingsFromFieldState(whatsapp.fields, {
      apiUrl: "https://api.green-api.com",
      apiTokenInstance: SECRET_MASK,
      timeoutSeconds: "10",
      allowInsecureHttp: "true",
    });
    assert.deepEqual(settings, {
      apiUrl: "https://api.green-api.com",
      apiTokenInstance: SECRET_MASK,
      timeoutSeconds: 10,
      allowInsecureHttp: true,
    });
    const seeded = fieldStateFromSettings(whatsapp.fields, {
      apiUrl: "https://api.green-api.com",
      apiTokenInstance: SECRET_MASK,
      allowInsecureHttp: true,
    });
    assert.equal(seeded.apiTokenInstance, SECRET_MASK);
    assert.equal(seeded.allowInsecureHttp, "true");
    assert.equal(seeded.timeoutSeconds, "");
  });

  it("rejects non-numeric number fields", () => {
    assert.throws(() => coerceFieldValue("number", "x"), /numeric/);
  });
});

describe("canSendTest / sendTestDisabledReason", () => {
  it("allows send-test when the type is in the catalog", () => {
    assert.equal(canSendTest([{ type_id: "webhook" }], "webhook"), true);
    assert.match(
      sendTestDisabledReason([{ type_id: "email" }], "webhook"),
      /not in the strategy catalog/i,
    );
  });

  it("rejects empty type and empty catalog", () => {
    assert.equal(canSendTest([{ type_id: "webhook" }], ""), false);
    assert.match(
      sendTestDisabledReason([], "webhook"),
      /No notification strategies/i,
    );
  });
});

describe("isSecretMask", () => {
  it("detects the redaction mask only", () => {
    assert.equal(isSecretMask(SECRET_MASK), true);
    assert.equal(isSecretMask("cleartext"), false);
  });
});
