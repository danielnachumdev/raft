import { statusTone, type StatusTone } from "./model/statusTone";
import "./StatusBadge.css";

/** Toned pill for a Compose status string (running / exited / …). */
export function StatusBadge(props: { value: string }) {
  const tone: StatusTone = statusTone(props.value);
  return (
    <span className={`status-badge tone-${tone}`} title={`Status: ${props.value}`}>
      {props.value}
    </span>
  );
}
