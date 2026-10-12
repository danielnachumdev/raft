import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "../chrome/Modal";
import type { AclEntry } from "./aclApi";

export type AclEntryFormSubmit = {
  id: string;
  cidr: string;
  comment: string;
};

type Props = {
  open: boolean;
  mode: "create" | "edit";
  entry: AclEntry | null;
  busy: boolean;
  onClose: () => void;
  onSubmit: (body: AclEntryFormSubmit) => void;
};

/** Modal to create or edit one CIDR ACL row. */
export function AclEntryFormModal(props: Props) {
  const [id, setId] = useState("");
  const [cidr, setCidr] = useState("");
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (!props.open) return;
    setId(props.entry?.id ?? "");
    setCidr(props.entry?.cidr ?? "");
    setComment(props.entry?.comment ?? "");
  }, [props.open, props.entry]);

  const title = props.mode === "create" ? "Add CIDR" : "Edit CIDR";
  const canSave = id.trim() !== "" && cidr.trim() !== "" && !props.busy;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSave) return;
    props.onSubmit({
      id: id.trim(),
      cidr: cidr.trim(),
      comment: comment.trim(),
    });
  }

  return (
    <Modal
      open={props.open}
      onClose={props.busy ? () => undefined : props.onClose}
      title={title}
      closeOnOverlay={!props.busy}
      footer={
        <div className="modal-actions">
          <button
            type="button"
            className="action-btn"
            disabled={props.busy}
            onClick={props.onClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="acl-entry-form"
            className={props.busy ? "action-btn is-loading" : "action-btn"}
            disabled={!canSave}
            aria-busy={props.busy}
            id="acl-entry-save"
          >
            {props.busy ? (
              <span className="spinner refresh-spinner" aria-hidden="true" />
            ) : null}
            Save
          </button>
        </div>
      }
    >
      <form id="acl-entry-form" className="acl-entry-form" onSubmit={onSubmit}>
        <label className="deploy-label">
          Id
          <input
            id="acl-entry-id"
            autoComplete="off"
            value={id}
            disabled={props.busy || props.mode === "edit"}
            onChange={(e) => setId(e.target.value)}
          />
        </label>
        <label className="deploy-label">
          CIDR / IP
          <input
            id="acl-entry-cidr"
            autoComplete="off"
            placeholder="192.0.2.0/24"
            value={cidr}
            disabled={props.busy}
            onChange={(e) => setCidr(e.target.value)}
          />
        </label>
        <label className="deploy-label">
          Comment
          <input
            id="acl-entry-comment"
            autoComplete="off"
            placeholder="optional"
            value={comment}
            disabled={props.busy}
            onChange={(e) => setComment(e.target.value)}
          />
        </label>
      </form>
    </Modal>
  );
}
