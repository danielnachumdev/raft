import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  accountCount,
  forceOauthInstructions,
  githubLoginHref,
  shouldAutoLoginGithub,
  usableAccounts,
  type GithubSession,
} from "../../../src/deploy/github/index.ts";

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

describe("githubLoginHref", () => {
  it("uses plain login for first connection", () => {
    assert.equal(githubLoginHref(), "/api/github/login");
  });

  it("uses add=1 so + can open the account-picker OAuth path", () => {
    assert.equal(githubLoginHref({ add: true }), "/api/github/login?add=1");
  });
});

describe("forceOauthInstructions", () => {
  it("detects add-service instructions query", () => {
    assert.equal(forceOauthInstructions("?instructions=1"), true);
    assert.equal(forceOauthInstructions("?setup=true"), true);
    assert.equal(forceOauthInstructions(""), false);
    assert.equal(forceOauthInstructions("?oauth_error=x"), false);
  });
});

describe("shouldAutoLoginGithub", () => {
  it("never auto-logins so delete sticks across refresh", () => {
    assert.equal(
      shouldAutoLoginGithub({
        session: sessionWith([]),
        oauthError: null,
        needsSetup: false,
      }),
      false,
    );
  });

  it("does not auto-login when accounts exist (including expired)", () => {
    assert.equal(
      shouldAutoLoginGithub({
        session: sessionWith([
          {
            id: "1",
            login: "demo-user",
            mock: false,
            expires_at: 1,
            expired: true,
          },
        ]),
        oauthError: null,
        needsSetup: false,
      }),
      false,
    );
  });
});
