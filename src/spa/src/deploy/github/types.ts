export type GithubOauthConfig = {
  oauth_configured: boolean;
  client_id_set: boolean;
  callback_url: string;
  oauth_app_url: string;
  docs_url: string;
  settings_path: string;
  application_name?: string;
  homepage_url?: string;
  description?: string;
  enable_device_flow?: boolean;
  expire_user_access_tokens?: boolean;
  scopes?: string;
  ok?: boolean;
  reloaded?: boolean;
};

export type GithubAccountPublic = {
  id: string;
  login: string;
  expires_at: number;
  expired?: boolean;
};

export type GithubSession = {
  authenticated: boolean;
  login?: string;
  expires_at?: number;
  accounts?: GithubAccountPublic[];
  active_account_id?: string | null;
  scopes?: string;
  hint?: string;
  oauth_configured?: boolean;
  client_id_set?: boolean;
  callback_url?: string;
  oauth_app_url?: string;
  docs_url?: string;
  settings_path?: string;
  application_name?: string;
  homepage_url?: string;
  description?: string;
  enable_device_flow?: boolean;
  expire_user_access_tokens?: boolean;
};

export type GithubRepo = {
  full_name: string;
  name: string;
  owner: string;
  private: boolean;
  default_branch: string;
  html_url: string;
};

export type DeployStep = {
  name: string;
  status: string;
  detail: string;
};

export type DeployNextStep = {
  title: string;
  body: string;
};

export type CiPrInfo = {
  status: string;
  detail: string;
  pr_url?: string;
};

export type DeployJob = {
  id: string;
  full_name: string;
  ref: string;
  status: string;
  error: string | null;
  app_name: string | null;
  steps: DeployStep[];
  next_steps: DeployNextStep[];
  deploy_pubkey: string | null;
  ci_pr: CiPrInfo | null;
  created_at: number;
};
