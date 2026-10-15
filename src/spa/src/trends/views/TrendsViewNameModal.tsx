import { useEffect, useState } from "react";
import { Modal } from "../../chrome/Modal";

export function TrendsViewNameModal(props: {
  open: boolean;
  title: string;
  initialName: string;
  confirmLabel: string;
  onConfirm: (name: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(props.initialName);

  useEffect(() => {
    if (props.open) setName(props.initialName);
  }, [props.open, props.initialName]);

  const trimmed = name.trim();
  const canSave = trimmed.length > 0;

  return (
    <Modal
      open={props.open}
      onClose={props.onCancel}
      title={props.title}
      footer={
        <div className="modal-actions">
          <button type="button" className="action-btn" onClick={props.onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="action-btn"
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
          aria-label="View name"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter" && canSave) props.onConfirm(trimmed);
          }}
        />
      </label>
    </Modal>
  );
}
