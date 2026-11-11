/** Form / YAML segmented control for draft document editors. */
export function ModeSwitch(props: {
  mode: "form" | "yaml";
  disabled?: boolean;
  /** Prefix for tab button ids (e.g. ``settings`` → ``settings-mode-form``). */
  idPrefix: string;
  onChange: (next: "form" | "yaml") => void;
}) {
  return (
    <div className="segmented" role="tablist" aria-label="Editor mode">
      {(["form", "yaml"] as const).map((value) => (
        <button
          key={value}
          type="button"
          role="tab"
          id={`${props.idPrefix}-mode-${value}`}
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
