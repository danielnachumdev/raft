import { SaveBar } from "../../shared/chrome/SaveBar";
import { ErrorState, LoadingState } from "../../shared/chrome/StateViews";
import { useUnsavedGuard } from "../../shared/chrome/useUnsavedGuard";
import {
  TemporaryOverrideBanner,
  unsavedTemporaryOverrideMessage,
} from "../../shared/gitops";
import { PageHeader } from "../../app/PageHeader";
import { RbacFormView } from "./RbacFormView";
import { RbacYamlPanel } from "./RbacYamlPanel";
import { RequirePermission } from "./RequirePermission";
import { useRbac } from "./RbacContext";
import { useRbacEditor } from "./useRbacEditor";
import type { EditorMode } from "./rbacDocument";
import "./RbacSettingsPage.css";

/** Roles and bindings editor (form + YAML). */
export function RbacSettingsPage() {
  const editor = useRbacEditor();
  const { can } = useRbac();
  const canWrite = can("rbac:write");
  useUnsavedGuard(editor.dirty && canWrite);

  const { draft, busy, saving, mode } = editor;
  const loading = busy && !draft;

  return (
    <div className="rbac-page">
      <PageHeader
        title="RBAC"
        subtitle="Who can use this dashboard and what they can do."
        actions={
          loading ? undefined : (
            <>
              <ModeSwitch
                mode={mode}
                disabled={busy || saving || !draft}
                onChange={(next) => void editor.switchMode(next)}
              />
              <button
                type="button"
                className="btn"
                id="rbac-reload"
                title="Discard local edits and reload"
                disabled={busy || saving}
                onClick={() => void editor.load()}
              >
                Reload
              </button>
              <RequirePermission permission="rbac:write" fallback={null}>
                <button
                  type="button"
                  className={
                    saving ? "btn btn-primary is-loading" : "btn btn-primary"
                  }
                  id="rbac-save"
                  disabled={busy || saving || !draft || !editor.dirty}
                  aria-busy={saving}
                  onClick={() => void editor.save()}
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              </RequirePermission>
            </>
          )
        }
      />

      {loading ? <LoadingState label="Loading…" id="rbac-loading" /> : null}

      {editor.error ? (
        <ErrorState
          message={editor.error}
          id="rbac-error"
          onRetry={draft ? undefined : () => void editor.load()}
        />
      ) : null}

      {draft ? (
        <div className="rbac-layout">
          <TemporaryOverrideBanner doc="rbac.yaml" id="rbac-temp-override" />
          {mode === "form" ? (
            <RbacFormView
              document={draft}
              catalog={editor.catalog}
              canWrite={canWrite}
              onChange={editor.setDocument}
            />
          ) : (
            <RbacYamlPanel
              value={editor.yamlText}
              onChange={editor.setYamlText}
              disabled={saving || !canWrite}
            />
          )}
          <RequirePermission permission="rbac:write" fallback={null}>
            <SaveBar
              open={editor.dirty}
              id="rbac-save-bar"
              message={unsavedTemporaryOverrideMessage()}
              saveLabel="Save"
              saving={saving}
              onSave={() => void editor.save()}
              onDiscard={() => void editor.load()}
            />
          </RequirePermission>
        </div>
      ) : null}
    </div>
  );
}

function ModeSwitch(props: {
  mode: EditorMode;
  disabled: boolean;
  onChange: (next: EditorMode) => void;
}) {
  return (
    <div className="segmented" role="tablist" aria-label="Editor mode">
      {(["form", "yaml"] as const).map((value) => (
        <button
          key={value}
          type="button"
          role="tab"
          id={`rbac-mode-${value}`}
          aria-selected={props.mode === value}
          disabled={props.disabled}
          onClick={() => props.onChange(value)}
        >
          {value === "form" ? "Form" : "YAML"}
        </button>
      ))}
    </div>
  );
}
