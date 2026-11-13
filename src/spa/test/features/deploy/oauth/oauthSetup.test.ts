import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  forceOauthInstructions,
  needsOauthSetup,
  oauthErrorFromSearch,
  type GithubSession,
} from "../../../../src/features/deploy/github/index.ts";
import {
  DEFAULT_APPLICATION_NAME,
  buildOauthAppCreateUrl,
  defaultOauthOrigin,
  resolveOauthSetupHints,
} from "../../../../src/features/deploy/oauth/oauthSetupHints.ts";

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

describe("forceOauthInstructions", () => {
  it("lets add-service re-show the checklist when configured", () => {
    assert.equal(forceOauthInstructions("?instructions=1"), true);
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
        client_id_set: false,
        callback_url: "https://ops.example.com/api/github/callback",
        homepage_url: "https://ops.example.com/",
        application_name: DEFAULT_APPLICATION_NAME,
        description: "Public raft dashboard — temporary GitHub login.",
        oauth_app_url: "https://github.com/settings/applications/new?x=1",
        settings_path: "/tmp/settings.yaml",
        enable_device_flow: false,
        expire_user_access_tokens: false,
      },
      null,
    );
    assert.equal(hints.application_name, DEFAULT_APPLICATION_NAME);
    assert.equal(hints.homepage_url, "https://ops.example.com/");
    assert.equal(
      hints.callback_url,
      "https://ops.example.com/api/github/callback",
    );
    assert.equal(hints.enable_device_flow, false);
    assert.equal(hints.expire_user_access_tokens, false);
    assert.match(hints.oauth_app_url, /applications\/new/);
  });

  it("falls back to localhost origin when window is loopback", () => {
    assert.equal(defaultOauthOrigin(8787), "http://127.0.0.1:8787");
  });
});
