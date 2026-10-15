import type { NotificationStrategyField } from "./notificationsApi";

type Props = {
  fields: NotificationStrategyField[];
  values: Record<string, string>;
  busy: boolean;
  onChange: (key: string, value: string) => void;
};

/** Renders catalog-declared settings inputs (secret → password). */
export function ChannelSettingsFields(props: Props) {
  return (
    <div className="channel-settings-fields" id="channel-settings-fields">
      {props.fields.map((field) => (
        <FieldRow
          key={field.key}
          field={field}
          value={props.values[field.key] ?? ""}
          busy={props.busy}
          onChange={(value) => props.onChange(field.key, value)}
        />
      ))}
    </div>
  );
}

function FieldRow(props: {
  field: NotificationStrategyField;
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
}) {
  const { field } = props;
  const inputId = `channel-setting-${field.key}`;
  if (field.kind === "checkbox") {
    return (
      <label className="channel-enabled">
        <input
          id={inputId}
          type="checkbox"
          checked={props.value === "true"}
          disabled={props.busy}
          onChange={(e) => props.onChange(e.target.checked ? "true" : "false")}
        />
        {field.label}
        {field.help ? <span className="muted channel-field-help">{field.help}</span> : null}
      </label>
    );
  }
  return (
    <label className="deploy-label">
      {field.label}
      {field.required ? " *" : ""}
      <input
        id={inputId}
        type={inputType(field.kind)}
        autoComplete={field.kind === "secret" ? "new-password" : "off"}
        value={props.value}
        disabled={props.busy}
        onChange={(e) => props.onChange(e.target.value)}
        placeholder={field.placeholder}
        required={field.required}
      />
      {field.help ? <span className="muted channel-field-help">{field.help}</span> : null}
    </label>
  );
}

function inputType(kind: string): string {
  if (kind === "secret") return "password";
  if (kind === "number") return "number";
  if (kind === "url") return "url";
  return "text";
}
