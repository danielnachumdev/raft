import type { GithubOauthConfig, GithubSession } from "../github/githubApi";

const OAUTH_APP_NEW = "https://github.com/settings/applications/new";

export const DEFAULT_APPLICATION_NAME = "raft serve";
export const DEFAULT_DESCRIPTION =
  "Localhost raft serve ops UI — temporary GitHub login to pick a repo and deploy.";

/** Concrete OAuth App form values shown in the serve setup checklist. */
export type OauthSetupHints = {
  application_name: string;
  homepage_url: string;
  description: string;
  callback_url: string;
  enable_device_flow: boolean;
  expire_user_access_tokens: boolean;
  oauth_app_url: string;
  settings_path: string;
  scopes: string;
};

/** Build a create-OAuth-App URL with best-effort Rails-style query prefills. */
export function buildOauthAppCreateUrl(input: {
  application_name: string;
  homepage_url: string;
  description: string;
  callback_url: string;
}): string {
  const params = new URLSearchParams();
  params.set("oauth_application[name]", input.application_name);
  params.set("oauth_application[url]", input.homepage_url);
  params.set("oauth_application[description]", input.description);
  params.set("oauth_application[callback_url]", input.callback_url);
  return `${OAUTH_APP_NEW}?${params.toString()}`;
}

export function resolveOauthSetupHints(
  config: GithubOauthConfig | null,
  session: GithubSession | null,
  port = 8787,
): OauthSetupHints {
  const homepage =
    config?.homepage_url ||
    session?.homepage_url ||
    `http://127.0.0.1:${port}/`;
  const callback =
    config?.callback_url ||
    session?.callback_url ||
    `http://127.0.0.1:${port}/api/github/callback`;
  const application_name =
    config?.application_name ||
    session?.application_name ||
    DEFAULT_APPLICATION_NAME;
  const description =
    config?.description || session?.description || DEFAULT_DESCRIPTION;
  const fromApi = config?.oauth_app_url || session?.oauth_app_url;
  return {
    application_name,
    homepage_url: homepage,
    description,
    callback_url: callback,
    enable_device_flow: config?.enable_device_flow ?? false,
    expire_user_access_tokens: config?.expire_user_access_tokens ?? false,
    oauth_app_url:
      fromApi ||
      buildOauthAppCreateUrl({
        application_name,
        homepage_url: homepage,
        description,
        callback_url: callback,
      }),
    settings_path:
      config?.settings_path || session?.settings_path || "~/.raft/settings.yaml",
    scopes: config?.scopes || session?.scopes || "read:user repo workflow",
  };
}
