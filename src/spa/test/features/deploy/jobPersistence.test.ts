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

function installMemorySessionStorage(): void {
  const store = new Map<string, string>();
  const memory: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key) {
      return store.has(key) ? store.get(key)! : null;
    },
    key(index) {
      return [...store.keys()][index] ?? null;
    },
    removeItem(key) {
      store.delete(key);
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: memory,
  });
}

describe("jobPersistence", () => {
  beforeEach(() => {
    installMemorySessionStorage();
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
