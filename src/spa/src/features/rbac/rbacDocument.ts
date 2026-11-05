import type { RbacBinding, RbacDocument, RbacRole } from "./rbacApi";

export const ADMIN_ROLE_ID = "admin";
const WILDCARD_READ = "*:read";
const WILDCARD_WRITE = "*:write";

export type EditorMode = "form" | "yaml";

export function emptyRbacDocument(): RbacDocument {
  return {
    version: 1,
    roles: [adminRole()],
    bindings: [],
  };
}

export function adminRole(): RbacRole {
  return {
    id: ADMIN_ROLE_ID,
    permissions: [WILDCARD_READ, WILDCARD_WRITE],
  };
}

export function isAdminRoleId(roleId: string): boolean {
  return roleId.trim().toLowerCase() === ADMIN_ROLE_ID;
}

/** Keep builtin admin first with full wildcards; drop duplicate admin entries. */
export function ensureAdminRole(doc: RbacDocument): RbacDocument {
  const others = doc.roles.filter((role) => !isAdminRoleId(role.id));
  return {
    ...doc,
    version: doc.version || 1,
    roles: [adminRole(), ...others],
  };
}

export function rbacDirty(args: {
  mode: EditorMode;
  draft: RbacDocument | null;
  savedJson: string;
  yamlText: string;
  yamlBaseline: string;
}): boolean {
  if (!args.draft) return false;
  if (args.mode === "yaml") return args.yamlText !== args.yamlBaseline;
  return JSON.stringify(args.draft) !== args.savedJson;
}

export function upsertRole(
  roles: RbacRole[],
  next: RbacRole,
  index: number | null,
): RbacRole[] {
  if (isAdminRoleId(next.id) && index == null) return roles;
  const cleaned = {
    id: next.id,
    permissions: [...new Set(next.permissions)],
  };
  if (index == null) {
    if (!cleaned.id.trim()) return roles;
    if (roles.some((role) => role.id === cleaned.id)) return roles;
    return [...roles, cleaned];
  }
  return roles.map((role, i) => {
    if (i !== index || isAdminRoleId(role.id)) return role;
    return cleaned;
  });
}

export function removeRoleAt(roles: RbacRole[], index: number): RbacRole[] {
  const target = roles[index];
  if (!target || isAdminRoleId(target.id)) return roles;
  return roles.filter((_, i) => i !== index);
}

export function upsertBinding(
  bindings: RbacBinding[],
  next: RbacBinding,
  index: number | null,
): RbacBinding[] {
  const cleaned = {
    subject: next.subject,
    role: next.role.trim() || next.role,
  };
  if (!cleaned.role) return bindings;
  if (index == null) return [...bindings, cleaned];
  return bindings.map((binding, i) => (i === index ? cleaned : binding));
}

export function removeBindingAt(
  bindings: RbacBinding[],
  index: number,
): RbacBinding[] {
  return bindings.filter((_, i) => i !== index);
}

/** Drop bindings that point at a removed role id. */
export function bindingsWithoutRole(
  bindings: RbacBinding[],
  roleId: string,
): RbacBinding[] {
  const key = roleId.trim().toLowerCase();
  return bindings.filter((b) => b.role.trim().toLowerCase() !== key);
}
