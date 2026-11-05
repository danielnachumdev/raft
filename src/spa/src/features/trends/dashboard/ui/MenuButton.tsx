import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import "./MenuButton.css";

export type MenuItem = {
  id: string;
  label: string;
  onSelect: () => void;
  hint?: string;
  danger?: boolean;
  disabled?: boolean;
  separatorBefore?: boolean;
};

/** Small popover menu (⋯ button): outside click / Escape close, arrow keys move. */
export function MenuButton(props: {
  label: string;
  items: MenuItem[];
  children?: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, rootRef, close);

  return (
    <div className={`menu-button ${props.className ?? ""}`} ref={rootRef}>
      <button
        type="button"
        className="menu-button-trigger"
        aria-label={props.label}
        title={props.label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        {props.children ?? <span aria-hidden="true">⋯</span>}
      </button>
      {open ? (
        <div className="menu-button-pop" role="menu" id={menuId} onKeyDown={moveFocus}>
          {props.items.map((item) => (
            <MenuRow key={item.id} item={item} onDone={close} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MenuRow(props: { item: MenuItem; onDone: () => void }) {
  const { item } = props;
  return (
    <>
      {item.separatorBefore ? <hr className="menu-button-sep" /> : null}
      <button
        type="button"
        role="menuitem"
        className={item.danger ? "menu-button-item is-danger" : "menu-button-item"}
        disabled={item.disabled}
        onClick={() => {
          props.onDone();
          item.onSelect();
        }}
      >
        <span>{item.label}</span>
        {item.hint ? <kbd className="menu-button-hint">{item.hint}</kbd> : null}
      </button>
    </>
  );
}

function useDismiss(
  open: boolean,
  rootRef: { current: HTMLDivElement | null },
  close: () => void,
): void {
  useEffect(() => {
    if (!open) return;
    rootRef.current
      ?.querySelector<HTMLButtonElement>(".menu-button-item:not(:disabled)")
      ?.focus();
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) close();
    };
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, rootRef, close]);
}

function moveFocus(event: KeyboardEvent<HTMLDivElement>): void {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  event.preventDefault();
  const items = [
    ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
      ".menu-button-item:not(:disabled)",
    ),
  ];
  const at = items.indexOf(document.activeElement as HTMLButtonElement);
  const step = event.key === "ArrowDown" ? 1 : -1;
  items[(at + step + items.length) % items.length]?.focus();
}
