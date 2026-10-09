import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  accountCount,
  usableAccounts,
  type GithubSession,
} from "../../src/deploy/githubApi.ts";

function sessionWith(
  accounts: GithubSession["accounts"],
): GithubSession {
  return {
    authenticated: (accounts ?? []).some((a) => !a.expired),
    accounts,
    active_account_id: accounts?.[0]?.id ?? null,
  };
}

describe("accountCount", () => {
  it("counts connected rows including expired", () => {
    assert.equal(accountCount(null), 0);
    assert.equal(
      accountCount(
        sessionWith([
          {
            id: "1",
            login: "demo-alice",
            mock: true,
            expires_at: 1,
            expired: true,
          },
          {
            id: "2",
            login: "demo-bob",
            mock: true,
            expires_at: 9e12,
          },
        ]),
      ),
      2,
    );
  });
});

describe("usableAccounts", () => {
  it("drops expired rows for the view-as dropdown", () => {
    const session = sessionWith([
      {
        id: "1",
        login: "demo-alice",
        mock: true,
        expires_at: 1,
        expired: true,
      },
      {
        id: "2",
        login: "demo-bob",
        mock: true,
        expires_at: 9e12,
      },
    ]);
    const usable = usableAccounts(session);
    assert.deepEqual(
      usable.map((a) => a.login),
      ["demo-bob"],
    );
  });

  it("returns empty when session missing", () => {
    assert.deepEqual(usableAccounts(null), []);
  });
});
