import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createLocalStorageAdapter } from "../../src/dashboard-kit/model/persistence.ts";
import { installMemoryStorage } from "../trends/memoryStorage.ts";

describe("dashboard-kit persistence adapter", () => {
  it("loads fallback when the key is missing or corrupt", () => {
    const memory = installMemoryStorage();
    const adapter = createLocalStorageAdapter<{ n: number }>({
      key: "raft-serve-kit-test",
      parse: (raw) =>
        raw && typeof raw === "object" && "n" in raw
          ? { n: (raw as { n: number }).n }
          : null,
      fallback: () => ({ n: 0 }),
    });
    assert.deepEqual(adapter.load(), { n: 0 });
    memory.set("raft-serve-kit-test", "{not-json");
    // setItem via map bypasses JSON; write corrupt through localStorage API
    localStorage.setItem("raft-serve-kit-test", "{not-json");
    assert.deepEqual(adapter.load(), { n: 0 });
  });

  it("round-trips a valid payload", () => {
    installMemoryStorage();
    const adapter = createLocalStorageAdapter<{ n: number }>({
      key: "raft-serve-kit-test",
      parse: (raw) =>
        raw && typeof raw === "object" && typeof (raw as { n: unknown }).n === "number"
          ? { n: (raw as { n: number }).n }
          : null,
      fallback: () => ({ n: 0 }),
    });
    adapter.save({ n: 7 });
    assert.deepEqual(adapter.load(), { n: 7 });
  });
});
