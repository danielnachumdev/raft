import { useState } from "react";
import { Modal } from "../../../chrome/Modal";

type Props = {
  open: boolean;
  title: string;
  initialName: string;
  confirmLabel: string;
  onConfirm: (name: string) => void;
  onCancel: () => void;
};

/** Name prompt for new / renamed dashboards (remounts per open). */
export function DashboardNameModal(props: Props) {
  if (!props.open) return null;
  return <NameModalBody {...props} />;
}

function NameModalBody(props: Props) {
  const [name, setName] = useState(props.initialName);
  const trimmed = name.trim();
  const canSave = trimmed.length > 0;

  return (
    <Modal
      open
      onClose={props.onCancel}
      title={props.title}
      footer={
        <div className="modal-actions">
          <button type="button" className="action-btn" onClick={props.onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="action-btn btn-primary"
            disabled={!canSave}
            onClick={() => {
              if (canSave) props.onConfirm(trimmed);
            }}
          >
            {props.confirmLabel}
          </button>
        </div>
      }
    >
      <label className="trends-field">
        <span>Name</span>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Dashboard name"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter" && canSave) props.onConfirm(trimmed);
          }}
        />
      </label>
    </Modal>
  );
}
