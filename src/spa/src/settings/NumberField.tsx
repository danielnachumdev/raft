/** Labeled number input bound to a settings draft field. */
export function NumberField(props: {
  id: string;
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  step?: number;
  hint?: string;
}) {
  return (
    <label className="field" htmlFor={props.id}>
      {props.label}
      <input
        id={props.id}
        type="number"
        value={Number.isFinite(props.value) ? props.value : 0}
        min={props.min}
        step={props.step ?? 1}
        onChange={(e) => props.onChange(Number(e.target.value))}
      />
      {props.hint ? <span className="form-hint">{props.hint}</span> : null}
    </label>
  );
}
