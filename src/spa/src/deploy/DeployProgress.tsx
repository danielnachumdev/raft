import { ServiceLogs } from "../logs/ServiceLogs";
import type { DeployJob } from "./githubApi";

export function DeployProgress(props: { job: DeployJob }) {
  const { job } = props;
  return (
    <section className="deploy-panel" id="deploy-progress">
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
          <p className="muted">
            Public deploy key (safe to copy; never share private keys):
          </p>
          <code className="deploy-pubkey-value">{job.deploy_pubkey}</code>
        </div>
      ) : null}
      {job.next_steps.length > 0 ? (
        <div className="next-steps" id="next-steps">
          <h3>Additional steps</h3>
          <p className="muted">
            Only what raft cannot do automatically (secrets, host paths, DNS/TLS,
            CI secrets).
          </p>
          <ul>
            {job.next_steps.map((step) => (
              <li key={step.title}>
                <strong>{step.title}</strong>
                <p>{step.body}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {job.app_name ? (
        <div className="deploy-logs" id="deploy-logs">
          <h3>Deployment logs</h3>
          <p className="muted">Container stdout/stderr for {job.app_name}.</p>
          <ServiceLogs service={job.app_name} />
        </div>
      ) : null}
    </section>
  );
}
