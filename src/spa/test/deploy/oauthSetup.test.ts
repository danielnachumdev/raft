import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  needsOauthSetup,
  oauthErrorFromSearch,
  type GithubSession,
} from "../../src/deploy/githubApi.ts";

describe("needsOauthSetup", () => {
  it("detects missing config from session", () => {
    const session: GithubSession = {
      authenticated: false,
      oauth_configured: false,
    };
    assert.equal(needsOauthSetup(session, null), true);
  });

  it("detects not-configured oauth_error text", () => {
    assert.equal(
      needsOauthSetup(null, "GitHub OAuth is not configured.\nFix: …"),
      true,
    );
  });

  it("skips when configured and no matching error", () => {
    const session: GithubSession = {
      authenticated: false,
      oauth_configured: true,
    };
    assert.equal(needsOauthSetup(session, "state mismatch"), false);
  });
});

describe("oauthErrorFromSearch", () => {
  it("reads oauth_error query", () => {
    const msg = oauthErrorFromSearch(
      "?oauth_error=" + encodeURIComponent("GitHub OAuth is not configured."),
    );
    assert.match(msg || "", /not configured/);
  });
});
