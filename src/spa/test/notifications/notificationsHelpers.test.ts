import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canSendTest,
  formatSettingsJson,
  isEmptyStrategyCatalog,
  isSecretMask,
  parseSettingsJson,
  sendTestDisabledReason,
  strategyTypeIds,
} from "../../src/notifications/notificationsHelpers.ts";
import { SECRET_MASK } from "../../src/notifications/notificationsApi.ts";

describe("isEmptyStrategyCatalog", () => {
  it("is true for an empty strategies list", () => {
    assert.equal(isEmptyStrategyCatalog([]), true);
  });

  it("is false when a type is registered", () => {
    assert.equal(isEmptyStrategyCatalog([{ type_id: "webhook" }]), false);
  });
});

describe("strategyTypeIds", () => {
  it("maps catalog entries without inventing types", () => {
    assert.deepEqual(
      strategyTypeIds([{ type_id: "webhook" }, { type_id: "email" }]),
      ["webhook", "email"],
    );
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

describe("canSendTest / sendTestDisabledReason", () => {
  it("stays disabled while send-test API is absent", () => {
    assert.equal(canSendTest([{ type_id: "webhook" }], "webhook"), false);
    assert.match(
      sendTestDisabledReason([{ type_id: "webhook" }], "webhook"),
      /not available yet/i,
    );
  });
});

describe("isSecretMask", () => {
  it("detects the redaction mask only", () => {
    assert.equal(isSecretMask(SECRET_MASK), true);
    assert.equal(isSecretMask("cleartext"), false);
  });
});
