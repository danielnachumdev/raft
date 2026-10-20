import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import {
  sectionOff,
  settingsDirty,
  settingsNavIds,
  SETTINGS_NAV_GROUPS,
} from "../../src/settings/settingsLayout.ts";
import type { SettingsDocument } from "../../src/settings/settingsApi.ts";

const sectionsDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../src/settings/sections",
);

const doc = (interval: number) =>
  ({ metrics: { interval } }) as unknown as SettingsDocument;

describe("settingsDirty", () => {
  const saved = JSON.stringify(doc(60));

  it("is clean before the document loads", () => {
    assert.equal(
      settingsDirty({ mode: "form", draft: null, savedJson: "", yamlText: "", yamlBaseline: "" }),
      false,
    );
  });

  it("tracks form edits against the saved document", () => {
    const base = { mode: "form" as const, savedJson: saved, yamlText: "", yamlBaseline: "" };
    assert.equal(settingsDirty({ ...base, draft: doc(60) }), false);
    assert.equal(settingsDirty({ ...base, draft: doc(90) }), true);
  });

  it("in YAML mode counts text edits and carried-over form edits", () => {
    const base = { mode: "yaml" as const, savedJson: saved, yamlBaseline: "a: 1\n" };
    assert.equal(settingsDirty({ ...base, draft: doc(60), yamlText: "a: 1\n" }), false);
    assert.equal(settingsDirty({ ...base, draft: doc(60), yamlText: "a: 2\n" }), true);
    assert.equal(settingsDirty({ ...base, draft: doc(90), yamlText: "a: 1\n" }), true);
  });
});

describe("settings section index", () => {
  it("links only to SectionCard ids that exist", () => {
    const sources = readdirSync(sectionsDir)
      .filter((name) => name.endsWith(".tsx"))
      .map((name) => readFileSync(join(sectionsDir, name), "utf8"))
      .join("\n");
    for (const id of settingsNavIds()) {
      assert.match(sources, new RegExp(`id="${id}"`), id);
    }
  });

  it("has unique ids across groups", () => {
    const ids = settingsNavIds();
    assert.equal(new Set(ids).size, ids.length);
    assert.ok(SETTINGS_NAV_GROUPS.every((g) => g.items.length > 0));
  });

  it("marks toggle-able sections off only when explicitly disabled", () => {
    const healing = { id: "settings-healing", label: "Healing", key: "healing" };
    const logging = { id: "settings-logging", label: "Logging" };
    assert.equal(sectionOff(healing, { healing: false }), true);
    assert.equal(sectionOff(healing, { healing: true }), false);
    assert.equal(sectionOff(healing, {}), false);
    assert.equal(sectionOff(logging, { logging: false }), false);
  });
});
