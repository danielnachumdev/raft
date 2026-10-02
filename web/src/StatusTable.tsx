import { useNavigate } from "react-router-dom";
import type { StatusRow } from "./api";
import { servicePath } from "./api";
import { ServiceQuickActions } from "./ServiceQuickActions";
import {
  parseMemoryRatioPercent,
  parsePercent,
  statusTone,
  utilTone,
  type StatusTone,
  type UtilTone,
} from "./statusTone";

const COLUMNS: { key: keyof StatusRow; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "role", label: "Role" },
  { key: "group", label: "Group" },
  { key: "status", label: "Status" },
  { key: "cpu", label: "CPU" },
  { key: "memory", label: "Memory" },
  { key: "uptime", label: "Uptime" },
];

export function StatusTable(props: {
  rows: StatusRow[];
  empty: string;
  onActionDone: () => void;
}) {
  const navigate = useNavigate();
  if (!props.rows.length) {
    return <p className="muted">{props.empty}</p>;
  }
  return (
    <table className="status-table">
      <thead>
        <tr>
          {COLUMNS.map((col) => (
            <th key={col.key}>{col.label}</th>
          ))}
          <th className="actions-col">Actions</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <StatusRowLink
            key={`${row.role}-${row.service}`}
            row={row}
            onOpen={() => navigate(servicePath(row.service))}
            onActionDone={props.onActionDone}
          />
        ))}
      </tbody>
    </table>
  );
}

function StatusRowLink(props: {
  row: StatusRow;
  onOpen: () => void;
  onActionDone: () => void;
}) {
  const { row, onOpen, onActionDone } = props;
  return (
    <tr
      className="status-row"
      tabIndex={0}
      role="link"
      aria-label={`Open ${row.name}`}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {COLUMNS.map((col) => (
        <td key={col.key}>{cellContent(col.key, row)}</td>
      ))}
      <td className="actions-col">
        <ServiceQuickActions
          service={row.service}
          name={row.name}
          onDone={onActionDone}
        />
      </td>
    </tr>
  );
}

function cellContent(key: keyof StatusRow, row: StatusRow) {
  const value = row[key];
  if (key === "status") {
    return <StatusBadge value={value} />;
  }
  if (key === "cpu") {
    return <UtilValue value={value} tone={utilTone(parsePercent(value))} />;
  }
  if (key === "memory") {
    return (
      <UtilValue value={value} tone={utilTone(parseMemoryRatioPercent(value))} />
    );
  }
  return value;
}

function StatusBadge(props: { value: string }) {
  const tone: StatusTone = statusTone(props.value);
  return (
    <span className={`status-badge tone-${tone}`} title={`Status: ${props.value}`}>
      {props.value}
    </span>
  );
}

function UtilValue(props: { value: string; tone: UtilTone }) {
  const className = props.tone ? `util-value util-${props.tone}` : "util-value";
  return <span className={className}>{props.value}</span>;
}
