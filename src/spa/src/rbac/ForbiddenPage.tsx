import { Link } from "react-router-dom";
import { PageHeader } from "../shell/PageHeader";

export function ForbiddenPage() {
  return (
    <div className="forbidden-page" id="forbidden-page">
      <PageHeader
        title="403 — Forbidden"
        subtitle="You are signed in but do not have permission for this page. Ask an admin to bind your subject in host/rbac.yaml (GitOps), then Sync."
        actions={
          <Link className="btn" to="/">
            Back to status
          </Link>
        }
      />
    </div>
  );
}
