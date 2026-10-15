import { FlashValue } from "../chrome/FlashValue";
import { solidFlash } from "../chrome/flashValue";
import { StatTile, StatTiles } from "../chrome/StatTile";
import type { StatusRow } from "../shared/api/index.ts";
import { summarizeStatus } from "../status/model/statusSummary";

const COUNT_FLASH = solidFlash({ intensity: 0.5 });

/** At-a-glance health tiles above the status tables. */
export function StatusSummary(props: { rows: StatusRow[] }) {
  const s = summarizeStatus(props.rows);
  const names = s.attentionNames.slice(0, 3).join(", ");
  const more = s.attentionNames.length > 3 ? ` +${s.attentionNames.length - 3}` : "";
  return (
    <StatTiles label="Stack health" id="status-summary">
      <StatTile
        label="Services"
        value={
          <FlashValue value={s.total} mode={COUNT_FLASH} className="flash-value--fill">
            {s.total}
          </FlashValue>
        }
      />
      <StatTile
        label="Running"
        value={
          <FlashValue value={s.running} mode={COUNT_FLASH} className="flash-value--fill">
            {s.running}
          </FlashValue>
        }
        tone={s.running ? "ok" : undefined}
      />
      <StatTile
        label="Needs attention"
        value={
          <FlashValue value={s.attention} mode={COUNT_FLASH} className="flash-value--fill">
            {s.attention}
          </FlashValue>
        }
        tone={s.attention ? "bad" : undefined}
        hint={s.attention ? `${names}${more}` : "All clear"}
      />
      <StatTile
        label="Scaled to zero"
        value={
          <FlashValue value={s.idle} mode={COUNT_FLASH} className="flash-value--fill">
            {s.idle}
          </FlashValue>
        }
        tone={s.idle ? "idle" : undefined}
        hint={s.idle ? "Wakes on next request" : undefined}
      />
    </StatTiles>
  );
}
