/** Labeled text input bound to a settings draft field. */
export function TextField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  hint?: string;
}) {
  return (
    <label className="field" htmlFor={props.id}>
      {props.label}
      <input
        id={props.id}
        type={props.type ?? "text"}
        value={props.value}
        placeholder={props.placeholder}
        onChange={(e) => props.onChange(e.target.value)}
        autoComplete="off"
      />
      {props.hint ? <span className="form-hint">{props.hint}</span> : null}
    </label>
  );
}
