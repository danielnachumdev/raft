import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import { aboutFactRows } from "../../src/settings/aboutFacts.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

describe("aboutFactRows", () => {
  it("shows version, short hostname, FQDN, and host facts from dummy status", () => {
    const rows = aboutFactRows(
      {
        hostname: "demo-host",
        fqdn: "demo-host.example.test",
        cpus: 4,
        loadavg: [0.82, 0.71, 0.66],
        uptime_seconds: 3661,
        memory: {
          used_bytes: 4 * 1024 ** 3,
          total_bytes: 8 * 1024 ** 3,
          used_percent: 50,
        },
        disk: {
          used_bytes: 40 * 1024 ** 3,
          total_bytes: 100 * 1024 ** 3,
          used_percent: 40,
        },
      },
      { package: "0.12.0", line: "raft 0.12.0", label: "0.12.0" },
    );
    const byLabel = Object.fromEntries(rows.map((r) => [r.label, r.value]));
    assert.equal(byLabel["raft version"], "raft 0.12.0");
    assert.equal(byLabel.Hostname, "demo-host");
    assert.equal(byLabel.FQDN, "demo-host.example.test");
    assert.equal(byLabel.CPUs, "4");
    assert.equal(byLabel["Load average"], "0.82 / 0.71 / 0.66");
    assert.match(byLabel.Memory, /4\.0 GiB \/ 8\.0 GiB/);
    assert.match(byLabel.Disk, /40\.0 GiB \/ 100 GiB/);
    assert.equal(byLabel.Uptime, "1h 1m");
  });

  it("omits FQDN when missing or identical to hostname", () => {
    const same = aboutFactRows({ hostname: "demo-host", fqdn: "demo-host" }, undefined);
    assert.ok(!same.some((r) => r.label === "FQDN"));
    const missing = aboutFactRows({ hostname: "demo-host" }, undefined);
    assert.ok(!missing.some((r) => r.label === "FQDN"));
  });
});

describe("Settings → About wiring", () => {
  it("registers a non-settings.yaml About section with status-backed facts", () => {
    const layout = readFileSync(
      join(root, "src/settings/settingsLayout.ts"),
      "utf8",
    );
    const page = readFileSync(join(root, "src/settings/SettingsPage.tsx"), "utf8");
    const section = readFileSync(
      join(root, "src/settings/sections/AboutSection.tsx"),
      "utf8",
    );
    assert.match(layout, /id: "settings-about"/);
    assert.match(page, /AboutSection/);
    assert.match(section, /id="settings-about"/);
    assert.match(section, /not part of settings\.yaml/);
    assert.match(section, /aboutFactRows/);
  });
});
