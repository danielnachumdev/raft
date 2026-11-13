import { ServiceLogs } from "../logs/ServiceLogs";
import type { DeployJob } from "./github/index.ts";

export function DeployProgress(props: { job: DeployJob }) {
  const { job } = props;
  const showLogs = job.status === "succeeded" && Boolean(job.app_name);
  const extraSteps = job.deploy_pubkey
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
      {job.deploy_pubkey ? (
        <div className="deploy-pubkey" id="deploy-pubkey">
          <h3>Add this deploy key on GitHub</h3>
          <p className="muted">
            Private repos need this read-only key before raft can clone over
            SSH. Paste it under Deploy keys, then retry deploy.
          </p>
          {job.deploy_key_url ? (
            <p>
              <a
                className="btn btn-primary deploy-cta"
                href={job.deploy_key_url}
                target="_blank"
                rel="noreferrer"
                id="deploy-key-open"
              >
                Open Deploy keys on GitHub
              </a>
            </p>
          ) : null}
          <code className="deploy-pubkey-value">{job.deploy_pubkey}</code>
        </div>
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
