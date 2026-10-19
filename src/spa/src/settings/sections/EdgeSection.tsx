import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import { TextField } from "../TextField";
import type { EdgeStream, SettingsDocument } from "../settingsApi";

export function EdgeSection(props: {
  value: SettingsDocument["edge"];
  onChange: (next: SettingsDocument["edge"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["edge"]>) =>
    props.onChange({ ...v, ...patch });

  return (
    <SectionCard
      id="settings-edge"
      title="Edge"
      hint={
        <>
          Public listeners published by the gate. Changing http / https / streams
          requires <code>raft gate recreate</code> (not reload).
        </>
      }
    >
      <div className="form-grid">
        <PortOrNullField
          id="edge-http"
          label="HTTP port"
          value={v.http}
          onChange={(http) => set({ http })}
        />
        <PortOrNullField
          id="edge-https"
          label="HTTPS port"
          value={v.https}
          onChange={(https) => set({ https })}
        />
      </div>
      <StreamsEditor
        streams={v.streams}
        onChange={(streams) => set({ streams })}
      />
    </SectionCard>
  );
}

function PortOrNullField(props: {
  id: string;
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const disabled = props.value === null;
  return (
    <div className="field">
      <span>{props.label}</span>
      <div className="settings-port-row">
        <label className="check">
          <input
            type="checkbox"
            checked={!disabled}
            onChange={(e) =>
              props.onChange(e.target.checked ? (props.id.includes("https") ? 443 : 80) : null)
            }
          />
          Published
        </label>
        <input
          id={props.id}
          type="number"
          min={1}
          max={65535}
          disabled={disabled}
          value={props.value ?? ""}
          onChange={(e) => props.onChange(Number(e.target.value))}
        />
      </div>
      <span className="form-hint">Uncheck to omit the listener (YAML null)</span>
    </div>
  );
}

function StreamsEditor(props: {
  streams: EdgeStream[];
  onChange: (streams: EdgeStream[]) => void;
}) {
  const update = (index: number, patch: Partial<EdgeStream>) => {
    props.onChange(
      props.streams.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  };
  return (
    <div className="settings-streams" id="edge-streams">
      <div className="settings-streams-head">
        <h3>Streams</h3>
        <button
          type="button"
          className="btn-secondary"
          id="edge-stream-add"
          onClick={() =>
            props.onChange([
              ...props.streams,
              { name: `stream-${props.streams.length + 1}`, port: 25, protocol: "tcp" },
            ])
          }
        >
          Add stream
        </button>
      </div>
      {props.streams.length === 0 ? (
        <p className="muted">No stream listeners. Add one for expose: stream apps.</p>
      ) : null}
      {props.streams.map((stream, index) => (
        <div className="settings-stream-row form-grid" key={`${stream.name}-${index}`}>
          <TextField
            id={`edge-stream-name-${index}`}
            label="Name"
            value={stream.name}
            onChange={(name) => update(index, { name })}
          />
          <NumberField
            id={`edge-stream-port-${index}`}
            label="Port"
            value={stream.port}
            min={1}
            onChange={(port) => update(index, { port })}
          />
          <label className="field" htmlFor={`edge-stream-proto-${index}`}>
            Protocol
            <select
              id={`edge-stream-proto-${index}`}
              value={stream.protocol}
              onChange={(e) => update(index, { protocol: e.target.value })}
            >
              <option value="tcp">tcp</option>
              <option value="udp">udp</option>
            </select>
          </label>
          <div className="field">
            <span className="settings-invisible">Remove</span>
            <button
              type="button"
              className="btn-secondary"
              onClick={() =>
                props.onChange(props.streams.filter((_, i) => i !== index))
              }
            >
              Remove
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
