import type { ReactNode } from "react";
import type { StatusRow } from "../shared/api/index.ts";
import { StatusTable } from "../status/StatusTable";

export function DashboardSection(props: {
  title: string;
  rows: StatusRow[];
  empty: ReactNode;
  storageKey: string;
  onActionDone: () => void;
  id?: string;
}) {
  return (
    <section className="panel" id={props.id}>
      <div className="panel-head">
        <h2>
          {props.title}
          {props.rows.length ? (
            <span className="panel-count">{props.rows.length}</span>
          ) : null}
        </h2>
      </div>
      <StatusTable
        rows={props.rows}
        empty={props.empty}
        storageKey={props.storageKey}
        onActionDone={props.onActionDone}
      />
    </section>
  );
}
