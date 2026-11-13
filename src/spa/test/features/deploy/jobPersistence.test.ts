import assert from "node:assert/strict";
import { describe, it, beforeEach } from "node:test";
import {
  clearPersistedDeployJob,
  isDeployInFlight,
  persistDeployJob,
  readPersistedDeployJobId,
} from "../../../src/features/deploy/model/jobPersistence.ts";
import type { DeployJob } from "../../../src/features/deploy/github/types.ts";

function job(partial: Partial<DeployJob>): DeployJob {
  return {
    id: "abc123",
    full_name: "demo/api",
    ref: "main",
    manifest_path: ".raft/app.yaml",
    status: "running",
    error: null,
    app_name: null,
    steps: [],
    next_steps: [],
    deploy_pubkey: null,
    ci_pr: null,
    created_at: 1,
    ...partial,
  };
}

describe("jobPersistence", () => {
  beforeEach(() => {
    clearPersistedDeployJob();
  });

  it("persists and reads the job id", () => {
    persistDeployJob(job({ id: "job-1" }));
    assert.equal(readPersistedDeployJobId(), "job-1");
  });

  it("clears the stored job id", () => {
    persistDeployJob(job({ id: "job-2" }));
    clearPersistedDeployJob();
    assert.equal(readPersistedDeployJobId(), null);
  });

  it("detects in-flight statuses", () => {
    assert.equal(isDeployInFlight(job({ status: "pending" })), true);
    assert.equal(isDeployInFlight(job({ status: "running" })), true);
    assert.equal(isDeployInFlight(job({ status: "failed" })), false);
    assert.equal(isDeployInFlight(null), false);
  });
});
