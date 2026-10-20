import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  applyVariablesToQuery,
  interpolateTitle,
  pinDraftToVariables,
  scopeFromVariables,
} from "../../src/dashboard-kit/model/variables.ts";

describe("dashboard-kit variables", () => {
  it("interpolates bound tokens and leaves unbound ones literal", () => {
    assert.equal(
      interpolateTitle("CPU · ${service}", { service: "demo-api" }),
      "CPU · demo-api",
    );
    assert.equal(
      interpolateTitle("${group} / ${service}", { group: "shop" }),
      "shop / ${service}",
    );
  });

  it("pins a query to the embed service variable", () => {
    const bound = applyVariablesToQuery(
      {
        metricIds: ["cpu_percent"],
        viewMode: "avg_all",
        selected: null,
      },
      { service: "demo-api" },
    );
    assert.deepEqual(bound, {
      metricIds: ["cpu_percent"],
      viewMode: "per_service",
      selected: ["demo-api"],
    });
  });

  it("derives fetch scope and pins drafts", () => {
    assert.deepEqual(scopeFromVariables({ service: "demo-api" }), {
      services: ["demo-api"],
    });
    assert.deepEqual(scopeFromVariables({}), {});
    const draft = pinDraftToVariables(
      {
        title: "${service} CPU",
        metricIds: ["cpu_percent"],
        viewMode: "per_group",
        selected: null,
        size: "half",
      },
      { service: "demo-api" },
    );
    assert.equal(draft.title, "demo-api CPU");
    assert.deepEqual(draft.selected, ["demo-api"]);
    assert.equal(draft.viewMode, "per_service");
  });
});
