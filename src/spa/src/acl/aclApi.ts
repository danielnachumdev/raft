/** Typed client for serve `/api/acl/*` (gate + per-App IP/CIDR ACL). */

export type AclMode = "off" | "whitelist" | "blacklist";

export type AclEntry = {
  id: string;
  cidr: string;
  comment: string;
};

export type AclPolicy = {
  mode: AclMode;
  entries: AclEntry[];
  applied?: boolean;
};

export type AclAppMeta = {
  supported: boolean;
  reason?: string;
  fix?: string;
  publicHost?: string;
  exposes?: string[];
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

async function jsonRequest<T>(
  url: string,
  init?: RequestInit,
  label = "request",
): Promise<T> {
  const res = await fetch(url, init);
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `${label} ${res.status}`);
  }
  return body as T;
}

export async function fetchGateAcl(): Promise<AclPolicy> {
  return jsonRequest("/api/acl/gate", undefined, "gate ACL");
}

export async function putGateAcl(body: AclPolicy): Promise<AclPolicy> {
  return jsonRequest(
    "/api/acl/gate",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: body.mode, entries: body.entries }),
    },
    "save gate ACL",
  );
}

export async function clearGateAcl(): Promise<AclPolicy> {
  return jsonRequest("/api/acl/gate", { method: "DELETE" }, "clear gate ACL");
}

export async function fetchAppAclMeta(name: string): Promise<AclAppMeta> {
  return jsonRequest(
    `/api/acl/apps/${encodeURIComponent(name)}/meta`,
    undefined,
    "app ACL meta",
  );
}

export async function fetchAppAcl(name: string): Promise<AclPolicy> {
  return jsonRequest(
    `/api/acl/apps/${encodeURIComponent(name)}`,
    undefined,
    "app ACL",
  );
}

export async function putAppAcl(
  name: string,
  body: AclPolicy,
): Promise<AclPolicy> {
  return jsonRequest(
    `/api/acl/apps/${encodeURIComponent(name)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: body.mode, entries: body.entries }),
    },
    "save app ACL",
  );
}

export async function clearAppAcl(name: string): Promise<AclPolicy> {
  return jsonRequest(
    `/api/acl/apps/${encodeURIComponent(name)}`,
    { method: "DELETE" },
    "clear app ACL",
  );
}
