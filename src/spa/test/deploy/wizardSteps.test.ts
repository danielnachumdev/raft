import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEPLOY_STEPS,
  currentStep,
  stepState,
} from "../../src/deploy/model/wizardSteps.ts";

describe("currentStep", () => {
  it("walks connect → pick → deploy → done", () => {
    assert.equal(currentStep(false, null, null), 0);
    assert.equal(currentStep(true, null, null), 1);
    assert.equal(currentStep(true, { full_name: "demo-org/demo-api" }, null), 2);
    assert.equal(currentStep(true, null, { status: "running" }), 2);
    assert.equal(
      currentStep(true, null, { status: "succeeded" }),
      DEPLOY_STEPS.length,
    );
  });

  it("keeps a failed deploy on the deploy step", () => {
    assert.equal(currentStep(true, null, { status: "failed" }), 2);
  });
});

describe("stepState", () => {
  it("marks earlier steps done and later steps todo", () => {
    assert.deepEqual(
      [0, 1, 2].map((i) => stepState(i, 1)),
      ["done", "current", "todo"],
    );
  });
});
