/** YAML editor for the full operator settings document. */

export function SettingsYamlPanel(props: {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="settings-yaml" id="settings-yaml">
      <p className="muted settings-yaml-hint">
        Edit the full <code>settings.yaml</code> document. Save validates with
        the same parsers as the form. Secrets show as <code>***</code>; leave
        the mask to keep the stored value.
      </p>
      <label className="field" htmlFor="settings-yaml-editor">
        YAML
        <textarea
          id="settings-yaml-editor"
          className="settings-yaml-editor"
          spellCheck={false}
          rows={28}
          disabled={props.disabled}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
        />
      </label>
    </div>
  );
}
