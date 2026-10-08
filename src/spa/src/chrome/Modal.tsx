import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import "./Modal.css";
export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  /** When false, overlay click does not dismiss (default true). */
  closeOnOverlay?: boolean;
};

/** Reusable dialog: overlay + panel, Escape / optional overlay dismiss, focus basics. */
export function Modal(props: ModalProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const closeOnOverlay = props.closeOnOverlay !== false;

  useEffect(() => {
    if (!props.open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    return () => {
      previousFocus.current?.focus();
    };
  }, [props.open]);

  useEffect(() => {
    if (!props.open) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        props.onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [props.open, props.onClose]);

  if (!props.open) return null;

  return createPortal(
    <div className="modal-overlay" onClick={onOverlayClick}>
      <div
        ref={panelRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onPanelTab}
        onClick={stopBubble}
      >
        <header className="modal-header">
          <h2 id={titleId} className="modal-title">
            {props.title}
          </h2>
          <button
            type="button"
            className="modal-close"
            aria-label="Close"
            onClick={props.onClose}
          >
            ×
          </button>
        </header>
        <div className="modal-body">{props.children}</div>
        {props.footer ? (
          <footer className="modal-footer">{props.footer}</footer>
        ) : null}
      </div>
    </div>,
    document.body,
  );

  function onOverlayClick() {
    if (closeOnOverlay) props.onClose();
  }
}

function stopBubble(event: MouseEvent) {
  event.stopPropagation();
}

function onPanelTab(event: KeyboardEvent<HTMLDivElement>) {
  if (event.key !== "Tab") return;
  const root = event.currentTarget;
  const focusable = root.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  );
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
