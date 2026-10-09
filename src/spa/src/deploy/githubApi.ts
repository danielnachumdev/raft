export type GithubOauthConfig = {
  oauth_configured: boolean;
  mock: boolean;
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

export type GithubSession = {
  authenticated: boolean;
  login?: string;
  mock?: boolean;
  expires_at?: number;
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

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function detailOf(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return null;
}

export async function fetchGithubSession(): Promise<GithubSession> {
  const res = await fetch("/api/github/session");
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `session ${res.status}`);
  }
  return body as GithubSession;
}

export async function logoutGithub(): Promise<void> {
  const res = await fetch("/api/github/logout", { method: "POST" });
  if (!res.ok) {
    const body = await readJson(res);
    throw new Error(detailOf(body) || `logout ${res.status}`);
  }
}

export async function fetchGithubConfig(): Promise<GithubOauthConfig> {
  const res = await fetch("/api/github/config");
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `config ${res.status}`);
  }
  return body as GithubOauthConfig;
}

export async function saveGithubConfig(input: {
  clientId: string;
  clientSecret: string;
}): Promise<GithubOauthConfig> {
  const res = await fetch("/api/github/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clientId: input.clientId,
      clientSecret: input.clientSecret,
    }),
  });
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `save config ${res.status}`);
  }
  return body as GithubOauthConfig;
}

export function needsOauthSetup(
  session: GithubSession | null,
  oauthError: string | null,
): boolean {
  if (session && session.oauth_configured === false) return true;
  if (!oauthError) return false;
  return /oauth is not configured/i.test(oauthError);
}

export async function fetchGithubRepos(q: string): Promise<GithubRepo[]> {
  const params = new URLSearchParams();
  if (q.trim()) params.set("q", q.trim());
  const res = await fetch(`/api/github/repos?${params.toString()}`);
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `repos ${res.status}`);
  }
  const repos = (body as { repos?: GithubRepo[] }).repos;
  return Array.isArray(repos) ? repos : [];
}

export async function startGithubDeploy(
  fullName: string,
  ref: string,
): Promise<DeployJob> {
  const res = await fetch("/api/github/deploy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName, ref }),
  });
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `deploy ${res.status}`);
  }
  return body as DeployJob;
}

export async function fetchDeployJob(id: string): Promise<DeployJob> {
  const res = await fetch(`/api/github/deploy/${encodeURIComponent(id)}`);
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `deploy status ${res.status}`);
  }
  return body as DeployJob;
}

export function oauthErrorFromSearch(search: string): string | null {
  const params = new URLSearchParams(search);
  const raw = params.get("oauth_error") || params.get("error");
  if (!raw || !raw.trim()) return null;
  try {
    return decodeURIComponent(raw.replace(/\+/g, " "));
  } catch {
    return raw;
  }
}
