import { StatTile, StatTiles } from "../chrome/StatTile";
import type { StatusRow } from "../shared/api/index.ts";
import { summarizeStatus } from "../status/model/statusSummary";

/** At-a-glance health tiles above the status tables. */
export function StatusSummary(props: { rows: StatusRow[] }) {
  const s = summarizeStatus(props.rows);
  const names = s.attentionNames.slice(0, 3).join(", ");
  const more = s.attentionNames.length > 3 ? ` +${s.attentionNames.length - 3}` : "";
  return (
    <StatTiles label="Stack health" id="status-summary">
      <StatTile label="Services" value={s.total} />
      <StatTile label="Running" value={s.running} tone={s.running ? "ok" : undefined} />
      <StatTile
        label="Needs attention"
        value={s.attention}
        tone={s.attention ? "bad" : undefined}
        hint={s.attention ? `${names}${more}` : "All clear"}
      />
      <StatTile
        label="Scaled to zero"
        value={s.idle}
        tone={s.idle ? "idle" : undefined}
        hint={s.idle ? "Wakes on next request" : undefined}
      />
    </StatTiles>
  );
}
