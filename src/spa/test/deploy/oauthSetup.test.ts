import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  needsOauthSetup,
  oauthErrorFromSearch,
  type GithubSession,
} from "../../src/deploy/githubApi.ts";
import {
  DEFAULT_APPLICATION_NAME,
  buildOauthAppCreateUrl,
  resolveOauthSetupHints,
} from "../../src/deploy/oauthSetupHints.ts";

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

describe("oauthSetupHints", () => {
  it("builds create URL with Rails-style query prefills", () => {
    const url = buildOauthAppCreateUrl({
      application_name: "raft serve",
      homepage_url: "http://127.0.0.1:8787/",
      description: "desc",
      callback_url: "http://127.0.0.1:8787/api/github/callback",
    });
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/settings/applications/new");
    assert.equal(parsed.searchParams.get("oauth_application[name]"), "raft serve");
    assert.equal(
      parsed.searchParams.get("oauth_application[url]"),
      "http://127.0.0.1:8787/",
    );
    assert.equal(
      parsed.searchParams.get("oauth_application[callback_url]"),
      "http://127.0.0.1:8787/api/github/callback",
    );
  });

  it("resolves concrete checklist values from config", () => {
    const hints = resolveOauthSetupHints(
      {
        oauth_configured: false,
        mock: false,
        client_id_set: false,
        callback_url: "http://127.0.0.1:9/api/github/callback",
        homepage_url: "http://127.0.0.1:9/",
        application_name: DEFAULT_APPLICATION_NAME,
        description: "Localhost raft serve ops UI — temporary GitHub login.",
        oauth_app_url: "https://github.com/settings/applications/new?x=1",
        settings_path: "/tmp/settings.yaml",
        enable_device_flow: false,
        expire_user_access_tokens: false,
      },
      null,
    );
    assert.equal(hints.application_name, DEFAULT_APPLICATION_NAME);
    assert.equal(hints.homepage_url, "http://127.0.0.1:9/");
    assert.equal(hints.enable_device_flow, false);
    assert.equal(hints.expire_user_access_tokens, false);
    assert.match(hints.oauth_app_url, /applications\/new/);
  });
});
