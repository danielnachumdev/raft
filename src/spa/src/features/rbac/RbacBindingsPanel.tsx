import { EmptyState } from "../../shared/chrome/StateViews";
import type { RbacBinding, RbacDocument } from "./rbacApi";
import { removeBindingAt, upsertBinding } from "./rbacDocument";

/** Subject → role bindings editor. */
export function RbacBindingsPanel(props: {
  document: RbacDocument;
  canWrite: boolean;
  onChange: (next: RbacDocument) => void;
}) {
  const roles = props.document.roles.map((role) => role.id);
  const bindings = props.document.bindings;

  const patch = (next: RbacBinding[]) => {
    props.onChange({ ...props.document, bindings: next });
  };

  const addBinding = () => {
    if (!props.canWrite) return;
    const role = roles.includes("admin") ? "admin" : (roles[0] ?? "admin");
    patch(
      upsertBinding(
        bindings,
        { subject: "", role },
        null,
      ),
    );
  };

  return (
    <section
      className="panel rbac-section"
      id="rbac-bindings"
      aria-labelledby="rbac-bindings-title"
    >
      <div className="panel-head">
        <h2 id="rbac-bindings-title">Bindings</h2>
        {props.canWrite ? (
          <div className="panel-head-actions">
            <button
              type="button"
              className="btn btn-sm"
              id="rbac-binding-add"
              onClick={addBinding}
            >
              Add binding
            </button>
          </div>
        ) : null}
      </div>

      {bindings.length === 0 ? (
        <EmptyState
          id="rbac-bindings-empty"
          title="No bindings yet."
          action={
            props.canWrite ? (
              <button
                type="button"
                className="btn btn-sm"
                id="rbac-binding-empty-add"
                onClick={addBinding}
              >
                Add binding
              </button>
            ) : undefined
          }
        >
          Map a subject to a role to grant dashboard access.
        </EmptyState>
      ) : null}

      <div className="rbac-bindings-list" id="rbac-bindings-list">
        {bindings.map((binding, index) => (
          <div className="rbac-binding-row form-grid" key={`binding-${index}`}>
            <label className="field" htmlFor={`rbac-binding-subject-${index}`}>
              Subject
              <input
                id={`rbac-binding-subject-${index}`}
                value={binding.subject}
                disabled={!props.canWrite}
                placeholder="ops@example.com"
                onChange={(e) =>
                  patch(
                    upsertBinding(
                      bindings,
                      { ...binding, subject: e.target.value },
                      index,
                    ),
                  )
                }
                autoComplete="off"
              />
            </label>
            <label className="field" htmlFor={`rbac-binding-role-${index}`}>
              Role
              <select
                id={`rbac-binding-role-${index}`}
                value={binding.role}
                disabled={!props.canWrite}
                onChange={(e) =>
                  patch(
                    upsertBinding(
                      bindings,
                      { ...binding, role: e.target.value },
                      index,
                    ),
                  )
                }
              >
                {!roles.includes(binding.role) ? (
                  <option value={binding.role}>{binding.role}</option>
                ) : null}
                {roles.map((roleId) => (
                  <option key={roleId} value={roleId}>
                    {roleId}
                  </option>
                ))}
              </select>
            </label>
            {props.canWrite ? (
              <div className="field">
                <span className="rbac-invisible">Remove</span>
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  id={`rbac-binding-remove-${index}`}
                  onClick={() => patch(removeBindingAt(bindings, index))}
                >
                  Remove
                </button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
