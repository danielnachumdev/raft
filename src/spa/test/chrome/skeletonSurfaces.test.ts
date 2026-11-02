import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");

function src(rel: string): string {
  return readFileSync(join(root, "src", rel), "utf8");
}

describe("skeleton cold-load surfaces", () => {
  it("uses plot skeleton for chart cold load (home + service graphs)", () => {
    const overlay = src("trends/chart/ChartLoadingOverlay.tsx");
    assert.match(overlay, /ChartPlotSkeleton/);
    assert.doesNotMatch(overlay, /is-cold/);
  });

  it("skeletons notifications, inbox, events, firewall, settings", () => {
    assert.match(
      src("notifications/NotificationsSettingsPage.tsx"),
      /ItemPanelSkeleton|showSkeleton/,
    );
    assert.match(src("inbox/InboxPage.tsx"), /ItemPanelSkeleton|showSkeleton/);
    assert.match(src("events/EventsPage.tsx"), /ItemListSkeleton|showSkeleton/);
    assert.match(
      src("firewall/FirewallSettingsPage.tsx"),
      /StatusTableSkeleton|FIREWALL_TABLE/,
    );
    assert.match(
      src("settings/SettingsPage.tsx"),
      /SettingsFormSkeleton|showSkeleton/,
    );
  });

  it("skeletons service page, HTTP inspection, and definition", () => {
    assert.match(
      src("service/ServicePage.tsx"),
      /ServicePageSkeleton|showSkeleton/,
    );
    assert.match(
      src("service/httpRequests/ServiceHttpRequests.tsx"),
      /StatusTableSkeleton|HTTP_REQUESTS_TABLE/,
    );
    assert.match(
      src("service/ServiceDefinition.tsx"),
      /SkeletonBone|showSkeleton/,
    );
  });
});
