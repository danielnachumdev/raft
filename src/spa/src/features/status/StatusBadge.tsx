import { statusTone, type StatusTone } from "./model/statusTone";
import "./StatusBadge.css";

const CHIP_TONE: Record<StatusTone, string> = {
  ok: "chip-ok",
  warn: "chip-warn",
  bad: "chip-bad",
  idle: "chip-idle",
  muted: "",
};

/** Toned pill for a Compose status string (running / exited / …). */
export function StatusBadge(props: { value: string }) {
  const tone: StatusTone = statusTone(props.value);
  const chipTone = CHIP_TONE[tone];
  const className = ["chip", "chip-dot", chipTone].filter(Boolean).join(" ");
  return (
    <span className={className} title={`Status: ${props.value}`}>
      {props.value}
    </span>
  );
}
