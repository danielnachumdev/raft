import type { RbacDocument } from "./rbacApi";
import { RbacBindingsPanel } from "./RbacBindingsPanel";
import { RbacRolesPanel } from "./RbacRolesPanel";

/** Form editor for roles and bindings. */
export function RbacFormView(props: {
  document: RbacDocument;
  catalog: string[];
  canWrite: boolean;
  onChange: (next: RbacDocument) => void;
}) {
  return (
    <div className="rbac-form" id="rbac-form">
      <RbacRolesPanel
        document={props.document}
        catalog={props.catalog}
        canWrite={props.canWrite}
        onChange={props.onChange}
      />
      <RbacBindingsPanel
        document={props.document}
        canWrite={props.canWrite}
        onChange={props.onChange}
      />
    </div>
  );
}
