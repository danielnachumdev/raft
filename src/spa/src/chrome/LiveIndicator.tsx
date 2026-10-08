import "./LiveIndicator.css";
export type LiveStatus = "live" | "connecting" | "offline";
type Props = {
  /** When true (and no `status`), shows the live pulse. */
  isLive: boolean;
  /** Overrides `isLive` when set — use for connecting / offline nuance. */
  status?: LiveStatus;
  /** Visible caption next to the blob; defaults from resolved status. */
  label?: string;
};

const LABELS: Record<LiveStatus, string> = {
  live: "Live",
  connecting: "Connecting",
  offline: "Paused",
};

/** Pulsating status blob for auto-refresh / streaming panels. */
export function LiveIndicator(props: Props) {
  const resolved = resolveStatus(props.isLive, props.status);
  const text = props.label ?? LABELS[resolved];
  return (
    <p
      className={`live-indicator live-indicator--${resolved}`}
      role="status"
      aria-live="polite"
    >
      <span className="live-indicator__blob" aria-hidden="true" />
      <span className="live-indicator__label">{text}</span>
    </p>
  );
}

function resolveStatus(isLive: boolean, status?: LiveStatus): LiveStatus {
  if (status !== undefined) return status;
  return isLive ? "live" : "offline";
}
