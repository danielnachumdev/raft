import { ModeSwitch } from "../../shared/chrome/ModeSwitch";
import { SaveBar } from "../../shared/chrome/SaveBar";
import { SettingsFormSkeleton, showSkeleton } from "../../shared/chrome/skeleton";
import { ErrorState } from "../../shared/chrome/StateViews";
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
import "./RbacSettingsPage.css";

/** Roles and bindings editor (form + YAML). */
export function RbacSettingsPage() {
  const editor = useRbacEditor();
  const { can } = useRbac();
  const canWrite = can("rbac:write");
  useUnsavedGuard(editor.dirty && canWrite);

  const { draft, busy, saving, mode } = editor;

  return (
    <div className="rbac-page">
      <PageHeader
        title="RBAC"
        subtitle="Who can use this dashboard and what they can do."
        actions={
          showSkeleton(busy, draft !== null) ? undefined : (
            <>
              <ModeSwitch
                mode={mode}
                idPrefix="rbac"
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
            </>
          )
        }
      />

      {showSkeleton(busy, draft !== null) ? (
        <SettingsFormSkeleton label="Loading RBAC…" id="rbac-loading" />
      ) : null}

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
