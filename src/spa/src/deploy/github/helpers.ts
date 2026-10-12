import type {
  GithubAccountPublic,
  GithubRepo,
  GithubSession,
} from "./types.ts";

export function needsOauthSetup(
  session: GithubSession | null,
  oauthError: string | null,
): boolean {
  if (session && session.oauth_configured === false) return true;
  if (!oauthError) return false;
  return /oauth is not configured/i.test(oauthError);
}

export function accountCount(session: GithubSession | null): number {
  return session?.accounts?.length ?? 0;
}

/** Non-expired connected accounts available for repo browse / deploy. */
export function usableAccounts(
  session: GithubSession | null,
): GithubAccountPublic[] {
  return (session?.accounts ?? []).filter((account) => !account.expired);
}

/** Local filter over the selected account’s repos (never global GH search). */
export function filterGithubRepos(
  repos: GithubRepo[],
  query: string,
): GithubRepo[] {
  const q = query.trim().toLowerCase();
  if (!q) return repos;
  return repos.filter((r) => r.full_name.toLowerCase().includes(q));
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
