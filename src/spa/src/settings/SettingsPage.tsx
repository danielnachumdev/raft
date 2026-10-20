import { useLocation } from "react-router-dom";
import { SaveBar } from "../chrome/SaveBar";
import { ErrorState, LoadingState } from "../chrome/StateViews";
import { useHashScroll } from "../chrome/useHashScroll";
import { useUnsavedGuard } from "../chrome/useUnsavedGuard";
import { PageHeader } from "../shell/PageHeader";
import { AppearanceSection } from "./sections/AppearanceSection";
import { UpdatesSection } from "./sections/UpdatesSection";
import { SettingsFormView } from "./SettingsFormView";
import { SettingsNotes } from "./SettingsNotes";
import { SettingsSectionNav } from "./SettingsSectionNav";
import { SettingsYamlPanel } from "./SettingsYamlPanel";
import { useSettingsEditor, type EditorMode } from "./useSettingsEditor";
import "./SettingsPage.css";

/** Full ``settings.yaml`` / RaftConfig editor for ``raft serve``. */
export function SettingsPage() {
  const editor = useSettingsEditor();
  const { draft, busy, saving, mode } = editor;
  useUnsavedGuard(editor.dirty);
  useHashScroll(useLocation().hash, !busy && draft !== null);

  return (
    <div className="settings-page">
      <PageHeader
        title="Settings"
        subtitle={
          <>
            Operator <code>settings.yaml</code> for this host — edit section by
            section, or switch to YAML for the whole document.
          </>
        }
        meta={
          editor.path ? (
            <code className="settings-path" title={editor.path}>
              {editor.path}
            </code>
          ) : undefined
        }
        actions={
          <>
            <ModeSwitch
              mode={mode}
              disabled={busy || saving || !draft}
              onChange={(next) => void editor.switchMode(next)}
            />
            <button
              type="button"
              className="btn"
              id="settings-reload"
              title="Discard local edits and reload settings.yaml"
              disabled={busy || saving}
              onClick={() => void editor.load()}
            >
              Reload
            </button>
            <button
              type="button"
              className={saving ? "btn btn-primary is-loading" : "btn btn-primary"}
              id="settings-save"
              disabled={busy || saving || !draft || !editor.dirty}
              aria-busy={saving}
              onClick={() => void editor.save()}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </>
        }
      />

      {busy ? <LoadingState label="Loading settings…" /> : null}

      {editor.error ? (
        <ErrorState
          message={editor.error}
          id="settings-error"
          onRetry={draft ? undefined : () => void editor.load()}
        />
      ) : null}

      {!busy && draft ? (
        <div className={mode === "form" ? "with-aside settings-layout" : "settings-layout"}>
          {mode === "form" ? <SettingsSectionNav enabled={editor.enabled} /> : null}
          <div className="settings-main">
            <SettingsNotes notes={editor.notes} />
            {mode === "form" ? (
              <>
                <AppearanceSection />
                <UpdatesSection />
                <SettingsFormView
                  draft={draft}
                  sections={editor.sections}
                  enabled={editor.enabled}
                  onPatch={editor.patch}
                  onEnabledChange={editor.setSectionEnabled}
                />
              </>
            ) : (
              <SettingsYamlPanel
                value={editor.yamlText}
                onChange={editor.setYamlText}
                disabled={saving}
              />
            )}
            <SaveBar
              open={editor.dirty}
              id="settings-save-bar"
              message="Unsaved changes to settings.yaml"
              saveLabel="Save"
              saving={saving}
              onSave={() => void editor.save()}
              onDiscard={() => void editor.load()}
            />
          </div>
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
          id={`settings-mode-${value}`}
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
