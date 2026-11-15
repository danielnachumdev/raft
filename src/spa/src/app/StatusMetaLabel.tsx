import { useEffect, useState } from "react";
import { statusMetaLabel } from "./statusMeta";

/** "Updated Xs ago" — owns the 1s clock so the tick re-renders only this label. */
export function StatusMetaLabel(props: {
  updating: boolean;
  fetchedAt: number | null;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (props.fetchedAt === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [props.fetchedAt]);

  const label = statusMetaLabel({ ...props, now });
  if (!label) return null;
  return (
    <span className="muted" aria-live="polite">
      {label}
    </span>
  );
}
