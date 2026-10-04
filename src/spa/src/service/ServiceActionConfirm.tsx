import { ConfirmPopup } from "../chrome/ConfirmPopup";
import type { ServiceActionRunner } from "./useServiceActionRunner";

/** Renders the pending stop/redeploy confirm from a service action runner. */
export function ServiceActionConfirm(props: {
  runner: ServiceActionRunner;
}) {
  const { confirm } = props.runner;
  if (!confirm) return null;
  return (
    <ConfirmPopup
      open
      title={confirm.title}
      message={confirm.message}
      confirmLabel={confirm.confirmLabel}
      danger={confirm.danger}
      onConfirm={props.runner.acceptConfirm}
      onCancel={props.runner.cancelConfirm}
    />
  );
}
