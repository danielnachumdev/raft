import { Link } from "react-router-dom";
import "./DeployPage.css";
import "./AddServicePage.css";

/** Choose how to add a service; v1 offers GitHub only. */
export function AddServicePage() {
  return (
    <div className="page add-service-page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Add new service</h1>
          <p className="muted header-updating">
            Pick a source. Serve stays localhost / SSH tunnel admin.
          </p>
        </div>
        <Link className="refresh" to="/">
          Stack status
        </Link>
      </header>

      <section className="deploy-panel" id="add-service-options">
        <h2>Options</h2>
        <ul className="add-service-options">
          <li>
            <Link
              className="add-service-option"
              to="/deploy"
              id="add-from-github"
            >
              <GithubMark />
              <span>
                <strong>Add from GitHub</strong>
                <span className="muted">
                  Authorize GitHub, pick a repo, deploy, and open a CI PR.
                </span>
              </span>
            </Link>
          </li>
        </ul>
      </section>
    </div>
  );
}

function GithubMark() {
  return (
    <svg
      className="github-mark"
      viewBox="0 0 16 16"
      width="28"
      height="28"
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
        0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
        -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87
        2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95
        0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82
        .64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82
        .44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75
        -3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38
        A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
      />
    </svg>
  );
}
