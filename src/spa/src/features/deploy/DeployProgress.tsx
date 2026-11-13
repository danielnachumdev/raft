import { ServiceLogs } from "../logs/ServiceLogs";
import { CopyableValue } from "./oauth/OauthSetupCopy";
import type { DeployJob } from "./github/index.ts";

export function DeployProgress(props: {
  job: DeployJob;
  busy?: boolean;
  onContinue?: () => void;
}) {
  const { job, busy = false, onContinue } = props;
  const showLogs = job.status === "succeeded" && Boolean(job.app_name);
  const showKeyPanel = Boolean(job.deploy_pubkey) && job.status === "failed";
  const canContinue = job.status === "failed" && Boolean(onContinue);
  const extraSteps = showKeyPanel
    ? job.next_steps.filter(
        (step) => !/deploy key/i.test(step.title) && !/deploy key/i.test(step.body),
      )
    : job.next_steps;
  return (
    <section className="panel deploy-panel" id="deploy-progress">
      <h2>Deploy progress</h2>
      <p>
        Status: <strong id="deploy-status">{job.status}</strong>
        {job.app_name ? (
          <>
            {" "}
            · app <code>{job.app_name}</code>
          </>
        ) : null}
      </p>
      <ul className="deploy-steps">
        {job.steps.map((step) => (
          <li key={step.name}>
            <strong>{step.name}</strong> — {step.status}
            {step.detail ? <span className="muted"> ({step.detail})</span> : null}
          </li>
        ))}
      </ul>
      {job.ci_pr ? (
        <div className="deploy-ci" id="deploy-ci">
          <h3>CI / PR</h3>
          <p>
            {job.ci_pr.status}: {job.ci_pr.detail}
            {job.ci_pr.pr_url ? (
              <>
                {" "}
                ·{" "}
                <a href={job.ci_pr.pr_url} target="_blank" rel="noreferrer">
                  Open PR
                </a>
              </>
            ) : null}
          </p>
        </div>
      ) : null}
      {job.error ? (
        <p className="error" role="alert" id="deploy-job-error">
          {job.error}
        </p>
      ) : null}
      {showKeyPanel ? (
        <div className="deploy-pubkey" id="deploy-pubkey">
          <h3>Add this deploy key on GitHub</h3>
          <p className="muted">
            GitHub cannot pre-fill Deploy keys. Copy Title and Key, open the
            form, paste both (read-only), then continue installation.
          </p>
          {job.deploy_key_title ? (
            <label className="field deploy-key-field" htmlFor="deploy-key-title">
              Title
              <CopyableValue
                id="deploy-key-title"
                value={job.deploy_key_title}
              />
            </label>
          ) : null}
          <label className="field deploy-key-field" htmlFor="deploy-key-pubkey">
            Key
            <CopyableValue id="deploy-key-pubkey" value={job.deploy_pubkey!} />
          </label>
          <div className="deploy-key-actions">
            {job.deploy_key_url ? (
              <a
                className="btn btn-primary deploy-cta"
                href={job.deploy_key_url}
                target="_blank"
                rel="noreferrer"
                id="deploy-key-open"
              >
                Open Deploy keys on GitHub
              </a>
            ) : null}
            {canContinue ? (
              <button
                type="button"
                className="btn btn-primary"
                id="deploy-continue"
                disabled={busy}
                onClick={() => onContinue?.()}
              >
                Continue installation
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      {!showKeyPanel && canContinue ? (
        <p className="deploy-key-actions">
          <button
            type="button"
            className="btn btn-primary"
            id="deploy-continue"
            disabled={busy}
            onClick={() => onContinue?.()}
          >
            Continue installation
          </button>
        </p>
      ) : null}
      {extraSteps.length > 0 ? (
        <div className="next-steps" id="next-steps">
          <h3>Additional steps</h3>
          <p className="muted">Follow these steps to finish the deploy.</p>
          <ul>
            {extraSteps.map((step) => (
              <li key={step.title}>
                <strong>{step.title}</strong>
                <p>{step.body}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {showLogs ? (
        <div className="deploy-logs" id="deploy-logs">
          <h3>Deployment logs</h3>
          <p className="muted">Container stdout/stderr for {job.app_name}.</p>
          <ServiceLogs service={job.app_name!} running />
        </div>
      ) : job.app_name ? (
        <div className="deploy-logs" id="deploy-logs-pending">
          <h3>Deployment logs</h3>
          <p className="muted">
            Container logs appear here after the App applies successfully.
            Until then, use the step list and messages above.
          </p>
        </div>
      ) : null}
    </section>
  );
}
