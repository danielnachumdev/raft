import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { DashboardKitContract } from "../../src/dashboard-kit/model/types.ts";
import { scopeFromVariables } from "../../src/dashboard-kit/model/variables.ts";

describe("dashboard-kit embed contract", () => {
  it("documents the overview embed shape used by Trends", () => {
    const overview: DashboardKitContract = {
      embedId: "trends",
      mode: "edit",
      chrome: { title: "Trends", showDashboardPicker: true },
    };
    assert.equal(overview.embedId, "trends");
    assert.equal(overview.mode, "edit");
    assert.equal(overview.chrome?.showDashboardPicker, true);
  });

  it("documents the service embed shape reserved for follow-on migration", () => {
    const service: DashboardKitContract = {
      embedId: "service-trends",
      mode: "edit",
      variables: { service: "demo-api" },
      scope: scopeFromVariables({ service: "demo-api" }),
      chrome: {
        title: "Trends",
        subtitle: "demo-api",
        showDashboardPicker: false,
        downloadServices: ["demo-api"],
      },
    };
    assert.deepEqual(service.scope, { services: ["demo-api"] });
    assert.equal(service.chrome?.showDashboardPicker, false);
  });
});
