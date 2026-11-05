import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  alertsListSkeletonPlan,
  chartFrameSkeletonPlan,
  chartPlotSkeletonPlan,
  DEFAULT_CHART_FRAME_HEIGHT,
  DEFAULT_ITEM_LIST_ROWS,
  DEFAULT_STAT_TILE_COUNT,
  DEFAULT_STATUS_TABLE_ROWS,
  FIREWALL_TABLE_BONE_WIDTHS,
  FIREWALL_TABLE_SKELETON_COLUMNS,
  HTTP_REQUESTS_TABLE_BONE_WIDTHS,
  HTTP_REQUESTS_TABLE_SKELETON_COLUMNS,
  itemListSkeletonPlan,
  stackStatusSkeletonPlan,
  STATUS_TABLE_BONE_WIDTHS,
  STATUS_TABLE_SKELETON_COLUMNS,
  statusTableSkeletonPlan,
  statTilesSkeletonPlan,
} from "../../../src/shared/chrome/skeleton/buildersConfig.ts";

describe("statusTableSkeletonPlan", () => {
  it("defaults to status columns and row count", () => {
    const plan = statusTableSkeletonPlan();
    assert.deepEqual(plan.columns, [...STATUS_TABLE_SKELETON_COLUMNS]);
    assert.equal(plan.rows, DEFAULT_STATUS_TABLE_ROWS);
    assert.equal(plan.boneWidths.length, plan.columns.length);
    assert.deepEqual(plan.boneWidths, [...STATUS_TABLE_BONE_WIDTHS]);
  });

  it("honors a custom row count", () => {
    assert.equal(statusTableSkeletonPlan({ rows: 2 }).rows, 2);
  });

  it("accepts firewall / HTTP column overrides", () => {
    const fw = statusTableSkeletonPlan({
      columns: FIREWALL_TABLE_SKELETON_COLUMNS,
      boneWidths: FIREWALL_TABLE_BONE_WIDTHS,
    });
    assert.equal(fw.columns.length, FIREWALL_TABLE_SKELETON_COLUMNS.length);
    assert.deepEqual(fw.boneWidths, [...FIREWALL_TABLE_BONE_WIDTHS]);

    const http = statusTableSkeletonPlan({
      columns: HTTP_REQUESTS_TABLE_SKELETON_COLUMNS,
      boneWidths: HTTP_REQUESTS_TABLE_BONE_WIDTHS,
    });
    assert.equal(
      http.columns.length,
      HTTP_REQUESTS_TABLE_SKELETON_COLUMNS.length,
    );
  });
});

describe("statTilesSkeletonPlan", () => {
  it("defaults to four health tiles", () => {
    assert.equal(statTilesSkeletonPlan().count, DEFAULT_STAT_TILE_COUNT);
    assert.equal(statTilesSkeletonPlan({ count: 6 }).count, 6);
  });
});

describe("itemListSkeletonPlan / alertsListSkeletonPlan", () => {
  it("share the default item-list row count", () => {
    assert.equal(itemListSkeletonPlan().rows, DEFAULT_ITEM_LIST_ROWS);
    assert.equal(alertsListSkeletonPlan().rows, DEFAULT_ITEM_LIST_ROWS);
    assert.equal(alertsListSkeletonPlan({ rows: 3 }).rows, 3);
  });
});

describe("chartFrameSkeletonPlan / chartPlotSkeletonPlan", () => {
  it("defaults chart frame and plot heights", () => {
    assert.equal(chartFrameSkeletonPlan().height, DEFAULT_CHART_FRAME_HEIGHT);
    assert.equal(chartFrameSkeletonPlan({ height: "10rem" }).height, "10rem");
    assert.equal(chartPlotSkeletonPlan().height, DEFAULT_CHART_FRAME_HEIGHT);
    assert.equal(chartPlotSkeletonPlan({ height: "14rem" }).height, "14rem");
  });
});

describe("stackStatusSkeletonPlan", () => {
  it("composes tiles + apps + control-plane row counts", () => {
    const plan = stackStatusSkeletonPlan();
    assert.equal(plan.tiles.count, DEFAULT_STAT_TILE_COUNT);
    assert.equal(plan.appsRows, 4);
    assert.equal(plan.controlPlaneRows, 3);

    const custom = stackStatusSkeletonPlan({
      tiles: 2,
      appsRows: 1,
      controlPlaneRows: 8,
    });
    assert.equal(custom.tiles.count, 2);
    assert.equal(custom.appsRows, 1);
    assert.equal(custom.controlPlaneRows, 8);
  });
});
