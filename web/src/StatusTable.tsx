import type { StatusRow } from "./api";

const COLUMNS: { key: keyof StatusRow; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "group", label: "Group" },
  { key: "status", label: "Status" },
  { key: "cpu", label: "CPU" },
  { key: "memory", label: "Memory" },
  { key: "uptime", label: "Uptime" },
];

export function StatusTable(props: { rows: StatusRow[]; empty: string }) {
  if (!props.rows.length) {
    return <p className="muted">{props.empty}</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          {COLUMNS.map((col) => (
            <th key={col.key}>{col.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr key={`${row.role}-${row.name}-${row.group}`}>
            {COLUMNS.map((col) => (
              <td key={col.key}>{row[col.key]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
