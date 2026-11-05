/** Keep in sync with raft.core.core.rbac.permissions.PermissionCodes. */

export const WILDCARD_READ = "*:read";
export const WILDCARD_WRITE = "*:write";

export function permissionMatches(granted: string, required: string): boolean {
  if (granted === required) return true;
  if (granted === WILDCARD_READ && required.endsWith(":read")) return true;
  if (granted === WILDCARD_WRITE && required.endsWith(":write")) return true;
  return false;
}

export function allows(
  granted: readonly string[],
  required: string,
): boolean {
  return granted.some((code) => permissionMatches(code, required));
}
