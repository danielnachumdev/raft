import { useSyncExternalStore, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import {
  getToasts,
  resolveToastActions,
  subscribeToasts,
  toast,
  type ToastAction,
  type ToastRecord,
} from "./toast";
import "./ToastHost.css";
/** Fixed bottom-right toast stack (subscribe to module store). */
export function ToastHost() {
  const items = useSyncExternalStore(subscribeToasts, getToasts, getToasts);
  return (
    <div className="toast-host">
      {items.map((item) => (
        <ToastItem key={item.id} item={item} />
      ))}
    </div>
  );
}

function ToastItem(props: { item: ToastRecord }) {
  const { item } = props;
  const actions = resolveToastActions(item);
  return (
    <div
      className={`toast toast--${item.type}`}
      role="status"
      aria-atomic="true"
    >
      {item.durationMs > 0 ? (
        <span
          className="toast__progress"
          aria-hidden="true"
          style={
            { "--toast-duration": `${item.durationMs}ms` } as CSSProperties
          }
        />
      ) : null}
      <span className="toast__swatch" aria-hidden="true" />
      <div className="toast__body">
        <p className="toast__message">{item.message}</p>
        {actions.length > 0 ? (
          <ToastActions itemId={item.id} actions={actions} />
        ) : null}
      </div>
      <button
        type="button"
        className="toast__dismiss"
        onClick={() => toast.dismiss(item.id)}
        aria-label="Dismiss notification"
      >
        ×
      </button>
    </div>
  );
}

function ToastActions(props: { itemId: string; actions: ToastAction[] }) {
  return (
    <div className="toast__actions">
      {props.actions.map((action) => (
        <ToastActionLink
          key={`${action.href}:${action.label}`}
          itemId={props.itemId}
          action={action}
        />
      ))}
    </div>
  );
}

function ToastActionLink(props: { itemId: string; action: ToastAction }) {
  const { itemId, action } = props;
  const onClick = () => toast.dismiss(itemId);
  if (action.external) {
    return (
      <a
        className="toast__link"
        href={action.href}
        target="_blank"
        rel="noreferrer"
        onClick={onClick}
      >
        {action.label}
      </a>
    );
  }
  return (
    <Link className="toast__link" to={action.href} onClick={onClick}>
      {action.label}
    </Link>
  );
}
