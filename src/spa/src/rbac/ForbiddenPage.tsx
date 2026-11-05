import { Link } from "react-router-dom";
import { PageHeader } from "../shell/PageHeader";

export function ForbiddenPage() {
  return (
    <div className="forbidden-page" id="forbidden-page">
      <PageHeader
        title="Access denied"
        subtitle="You don't have permission to view this page."
        actions={
          <Link className="btn" to="/">
            Back to status
          </Link>
        }
      />
    </div>
  );
}
