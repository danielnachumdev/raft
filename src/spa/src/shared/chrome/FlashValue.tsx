import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  solidFlash,
  type FlashMode,
  type FlashSignal,
} from "./flashValue";
import "./FlashValue.css";

const DEFAULT_MODE = solidFlash();
const DEFAULT_DURATION_MS = 700;

type Props = {
  /** Compared across renders; flash when this changes. */
  value: unknown;
  children: ReactNode;
  /** Declarative wash strategy; defaults to a subtle accent solid flash. */
  mode?: FlashMode;
  className?: string;
  /** Animation length in ms (ignored when reduced-motion). */
  durationMs?: number;
};

type ActiveFlash = FlashSignal & { key: number };

/**
 * Wraps live numeric (or stringified) content and washes the background when
 * `value` updates. Compose with {@link solidFlash} / {@link directionalFlash}.
 */
export function FlashValue(props: Props) {
  const durationMs = props.durationMs ?? DEFAULT_DURATION_MS;
  const modeRef = useRef(props.mode ?? DEFAULT_MODE);
  modeRef.current = props.mode ?? DEFAULT_MODE;
  const prevRef = useRef<{ ready: boolean; value: unknown }>({
    ready: false,
    value: props.value,
  });
  const [flash, setFlash] = useState<ActiveFlash | null>(null);
  const flashKey = useRef(0);

  useEffect(() => {
    const prev = prevRef.current;
    if (!prev.ready) {
      prev.ready = true;
      prev.value = props.value;
      return;
    }
    if (Object.is(prev.value, props.value)) return;
    const signal = modeRef.current.signal(prev.value, props.value);
    prev.value = props.value;
    if (!signal || signal.intensity <= 0) return;
    if (prefersReducedMotion()) return;
    flashKey.current += 1;
    setFlash({ ...signal, key: flashKey.current });
  }, [props.value]);

  useEffect(() => {
    if (!flash) return;
    const id = window.setTimeout(() => setFlash(null), durationMs);
    return () => window.clearTimeout(id);
  }, [flash, durationMs]);

  const className = [
    "flash-value",
    flash ? "flash-value--active" : "",
    flash ? `flash-value--${flash.direction}` : "",
    props.className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  const style = flash
    ? ({
        ["--flash-color" as string]: flash.color,
        ["--flash-intensity" as string]: String(flash.intensity),
        ["--flash-duration" as string]: `${durationMs}ms`,
      } satisfies CSSProperties)
    : undefined;

  return (
    <span className={className} style={style} data-flash-key={flash?.key}>
      {props.children}
    </span>
  );
}

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
