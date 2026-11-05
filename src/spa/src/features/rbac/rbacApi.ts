export type RbacRole = { id: string; permissions: string[] };
export type RbacBinding = { subject: string; role: string };
export type RbacDocument = {
  version: number;
  roles: RbacRole[];
  bindings: RbacBinding[];
};

export type RbacPutResult = {
  document: RbacDocument;
  gitops?: { temporary_override?: string };
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

export async function getRbac(): Promise<RbacDocument> {
  return jsonRequest<RbacDocument>("/api/rbac", undefined, "rbac");
}

export async function putRbac(doc: RbacDocument): Promise<RbacPutResult> {
  return jsonRequest<RbacPutResult>(
    "/api/rbac",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(doc),
    },
    "save rbac",
  );
}

export async function getRbacCatalog(): Promise<string[]> {
  const body = await jsonRequest<{ permissions?: string[] }>(
    "/api/rbac/catalog",
    undefined,
    "rbac catalog",
  );
  return body.permissions ?? [];
}

export async function encodeRbacYaml(
  document: RbacDocument,
): Promise<{ yaml: string; document: RbacDocument }> {
  return jsonRequest(
    "/api/rbac/yaml/encode",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document }),
    },
    "encode rbac yaml",
  );
}

export async function decodeRbacYaml(
  yaml: string,
): Promise<{ document: RbacDocument }> {
  return jsonRequest(
    "/api/rbac/yaml/decode",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml }),
    },
    "decode rbac yaml",
  );
}
