import { useState } from "react";
import type { RbacDocument, RbacRole } from "./rbacApi";
import {
  isAdminRoleId,
  removeRoleAt,
  upsertRole,
  bindingsWithoutRole,
} from "./rbacDocument";

/** Roles list + editor; builtin admin is locked. */
export function RbacRolesPanel(props: {
  document: RbacDocument;
  catalog: string[];
  canWrite: boolean;
  onChange: (next: RbacDocument) => void;
}) {
  const [selected, setSelected] = useState<number>(0);
  const roles = props.document.roles;
  const index = Math.min(selected, Math.max(roles.length - 1, 0));
  const role = roles[index] ?? null;
  const locked = role ? isAdminRoleId(role.id) : false;

  const patchRoles = (nextRoles: RbacRole[]) => {
    props.onChange({ ...props.document, roles: nextRoles });
  };

  const addRole = () => {
    if (!props.canWrite) return;
    const id = uniqueRoleId(roles);
    const next = upsertRole(roles, { id, permissions: [] }, null);
    patchRoles(next);
    setSelected(next.length - 1);
  };

  const removeSelected = () => {
    if (!props.canWrite || !role || locked) return;
    const nextRoles = removeRoleAt(roles, index);
    props.onChange({
      ...props.document,
      roles: nextRoles,
      bindings: bindingsWithoutRole(props.document.bindings, role.id),
    });
    setSelected(Math.max(0, index - 1));
  };

  return (
    <section className="panel rbac-section" id="rbac-roles" aria-labelledby="rbac-roles-title">
      <header className="rbac-section-head">
        <h2 id="rbac-roles-title">Roles</h2>
        {props.canWrite ? (
          <button type="button" className="btn btn-sm" id="rbac-role-add" onClick={addRole}>
            Add role
          </button>
        ) : null}
      </header>

      <div className="rbac-roles-layout">
        <ul className="rbac-role-list" id="rbac-role-list">
          {roles.map((item, i) => (
            <li key={`${item.id}-${i}`}>
              <button
                type="button"
                className={
                  i === index
                    ? "rbac-role-item is-selected"
                    : "rbac-role-item"
                }
                id={`rbac-role-${item.id}`}
                onClick={() => setSelected(i)}
              >
                <span>{item.id}</span>
                {isAdminRoleId(item.id) ? (
                  <span className="chip">Built-in</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>

        {role ? (
          <div className="rbac-role-editor" id="rbac-role-editor">
            <label className="field" htmlFor="rbac-role-id">
              Role id
              <input
                id="rbac-role-id"
                value={role.id}
                disabled={!props.canWrite || locked}
                onChange={(e) =>
                  patchRoles(
                    upsertRole(
                      roles,
                      { ...role, id: e.target.value },
                      index,
                    ),
                  )
                }
                autoComplete="off"
              />
            </label>

            <fieldset className="rbac-perm-fieldset" disabled={!props.canWrite || locked}>
              <legend>Permissions</legend>
              <div className="rbac-perm-grid" id="rbac-role-permissions">
                {props.catalog.map((code) => {
                  const checked = locked || role.permissions.includes(code);
                  return (
                    <label key={code} className="rbac-perm-item" htmlFor={`rbac-perm-${code}`}>
                      <input
                        id={`rbac-perm-${code}`}
                        type="checkbox"
                        checked={checked}
                        disabled={!props.canWrite || locked}
                        onChange={(e) =>
                          patchRoles(
                            upsertRole(
                              roles,
                              {
                                ...role,
                                permissions: togglePerm(
                                  role.permissions,
                                  code,
                                  e.target.checked,
                                ),
                              },
                              index,
                            ),
                          )
                        }
                      />
                      <code>{code}</code>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            {props.canWrite && !locked ? (
              <button
                type="button"
                className="btn btn-sm btn-danger"
                id="rbac-role-remove"
                onClick={removeSelected}
              >
                Remove role
              </button>
            ) : null}
            {locked ? (
              <p className="muted rbac-locked-note" id="rbac-admin-locked">
                Built-in role with full access.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="muted">No roles yet.</p>
        )}
      </div>
    </section>
  );
}

function togglePerm(perms: string[], code: string, on: boolean): string[] {
  if (on) return [...new Set([...perms, code])];
  return perms.filter((p) => p !== code);
}

function uniqueRoleId(roles: RbacRole[]): string {
  const taken = new Set(roles.map((r) => r.id.toLowerCase()));
  if (!taken.has("viewer")) return "viewer";
  let n = 2;
  while (taken.has(`role-${n}`)) n += 1;
  return `role-${n}`;
}
