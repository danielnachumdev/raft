import { detailFromBody, readJsonBody } from "../../shared/api/http.ts";
import {
  appResourceCache,
  CachedResourceProxy,
  resourceId,
} from "../../shared/cache/index.ts";
import type {
  DeployJob,
  GithubOauthConfig,
  GithubRepo,
  GithubSession,
} from "./types.ts";

const sessionProxy = new CachedResourceProxy(
  appResourceCache,
  resourceId("github", "session"),
  {
    read: async () => {
      const res = await fetch("/api/github/session");
      const body = await readJsonBody(res);
      if (!res.ok) {
        throw new Error(detailFromBody(body) || `session ${res.status}`);
      }
      return body as GithubSession;
    },
  },
);

const configProxy = new CachedResourceProxy(
  appResourceCache,
  resourceId("github", "config"),
  {
    read: async () => {
      const res = await fetch("/api/github/config");
      const body = await readJsonBody(res);
      if (!res.ok) {
        throw new Error(detailFromBody(body) || `config ${res.status}`);
      }
      return body as GithubOauthConfig;
    },
  },
);

const reposProxy = new CachedResourceProxy(
  appResourceCache,
  resourceId("github", "repos"),
  {
    read: async () => {
      const res = await fetch("/api/github/repos");
      const body = await readJsonBody(res);
      if (!res.ok) {
        throw new Error(detailFromBody(body) || `repos ${res.status}`);
      }
      const repos = (body as { repos?: GithubRepo[] }).repos;
      return Array.isArray(repos) ? repos : [];
    },
  },
);

export async function fetchGithubSession(): Promise<GithubSession> {
  return sessionProxy.read();
}

export async function logoutGithub(): Promise<GithubSession> {
  const next = await sessionProxy.write(async () => {
    const res = await fetch("/api/github/logout", { method: "POST" });
    const body = await readJsonBody(res);
    if (!res.ok) {
      throw new Error(detailFromBody(body) || `logout ${res.status}`);
    }
    return body as GithubSession;
  });
  reposProxy.invalidate();
  return next;
}

/** Hard-delete one connected account from durable serve state. */
export async function deleteGithubAccount(
  accountId: string,
): Promise<GithubSession> {
  const next = await sessionProxy.write(async () => {
    const res = await fetch(
      `/api/github/accounts/${encodeURIComponent(accountId)}`,
      { method: "DELETE" },
    );
    const body = await readJsonBody(res);
    if (!res.ok) {
      throw new Error(detailFromBody(body) || `delete account ${res.status}`);
    }
    return body as GithubSession;
  });
  reposProxy.invalidate();
  return next;
}

export async function selectGithubAccount(
  accountId: string,
): Promise<GithubSession> {
  const next = await sessionProxy.write(async () => {
    const res = await fetch("/api/github/accounts/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId }),
    });
    const body = await readJsonBody(res);
    if (!res.ok) {
      throw new Error(detailFromBody(body) || `select account ${res.status}`);
    }
    return body as GithubSession;
  });
  reposProxy.invalidate();
  return next;
}

export async function fetchGithubConfig(): Promise<GithubOauthConfig> {
  return configProxy.read();
}

export async function saveGithubConfig(input: {
  clientId: string;
  clientSecret: string;
}): Promise<GithubOauthConfig> {
  return configProxy.write(async () => {
    const res = await fetch("/api/github/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: input.clientId,
        clientSecret: input.clientSecret,
      }),
    });
    const body = await readJsonBody(res);
    if (!res.ok) {
      throw new Error(detailFromBody(body) || `save config ${res.status}`);
    }
    return body as GithubOauthConfig;
  });
}

/** Fetch the selected account’s owned/member repos (affiliation-scoped). */
export async function fetchGithubRepos(): Promise<GithubRepo[]> {
  return reposProxy.read();
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
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `deploy ${res.status}`);
  }
  return body as DeployJob;
}

export async function fetchDeployJob(id: string): Promise<DeployJob> {
  const res = await fetch(`/api/github/deploy/${encodeURIComponent(id)}`);
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `deploy status ${res.status}`);
  }
  return body as DeployJob;
}
