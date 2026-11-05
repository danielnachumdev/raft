import { DEPLOY_STEPS, stepState } from "./model/wizardSteps";
import "./DeploySteps.css";

/** Horizontal progress indicator for the GitHub add-service flow. */
export function DeploySteps(props: { current: number }) {
  return (
    <ol className="deploy-steps-bar" aria-label="Progress">
      {DEPLOY_STEPS.map((label, index) => {
        const state = stepState(index, props.current);
        return (
          <li
            key={label}
            className={`deploy-step deploy-step--${state}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="deploy-step-dot" aria-hidden="true">
              {state === "done" ? "✓" : index + 1}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
