export type RbacRole = { id: string; permissions: string[] };
export type RbacBinding = { subject: string; role: string };
export type RbacDocument = {
  version: number;
  roles: RbacRole[];
  bindings: RbacBinding[];
};

export async function getRbac(): Promise<RbacDocument> {
  const res = await fetch("/api/rbac");
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function putRbac(
  doc: RbacDocument,
): Promise<{ document: RbacDocument; gitops?: { temporary_override?: string } }> {
  const res = await fetch("/api/rbac", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRbacCatalog(): Promise<string[]> {
  const res = await fetch("/api/rbac/catalog");
  if (!res.ok) throw new Error(await res.text());
  const body = await res.json();
  return body.permissions ?? [];
}
