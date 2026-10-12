import { Link } from "react-router-dom";
import { LiveIndicator } from "../chrome/LiveIndicator";
import type { StatusRow } from "../shared/api/index.ts";
import { StatusTable } from "../status/StatusTable";

export function DashboardSection(props: {
  title: string;
  rows: StatusRow[];
  empty: string;
  storageKey: string;
  isLive: boolean;
  onActionDone: () => void;
  addHref?: string;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{props.title}</h2>
        <div className="panel-head-actions">
          {props.addHref ? (
            <Link
              className="panel-add"
              to={props.addHref}
              aria-label="Add new service"
              id="add-service"
              title="Add new service"
            >
              +
            </Link>
          ) : null}
          <LiveIndicator
            isLive={props.isLive}
            label={props.isLive ? undefined : "Paused · tab hidden"}
          />
        </div>
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
