import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="page-block">
      <h1>403 — Forbidden</h1>
      <p className="muted">
        You are signed in but do not have permission for this page. Ask an admin
        to bind your subject in host/rbac.yaml (GitOps), then Sync.
      </p>
      <p>
        <Link className="btn btn-sm" to="/">
          Back to status
        </Link>
      </p>
    </div>
  );
}
