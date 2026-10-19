import type { SettingsNote } from "./settingsApi";

/** Side-effect / guidance notes from GET/PUT ``/api/settings``. */
export function SettingsNotes(props: { notes: SettingsNote[] }) {
  if (!props.notes.length) return null;
  return (
    <ul className="settings-notes" id="settings-notes">
      {props.notes.map((note) => (
        <li
          key={note.code}
          className={
            note.severity === "warn"
              ? "callout callout-warn settings-note"
              : "callout settings-note"
          }
        >
          <strong>{note.code}</strong>
          <p className="muted">{note.message}</p>
        </li>
      ))}
    </ul>
  );
}
