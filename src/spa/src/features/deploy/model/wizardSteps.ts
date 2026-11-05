/** GitHub add-service wizard position (connect → pick → deploy). */

export const DEPLOY_STEPS = ["Connect GitHub", "Pick repository", "Deploy"] as const;

export type DeployStepState = "done" | "current" | "todo";

/** Index of the active step; ``DEPLOY_STEPS.length`` once deploy succeeded. */
export function currentStep(
  connected: boolean,
  selected: unknown,
  job: { status: string } | null,
): number {
  if (!connected) return 0;
  if (job?.status === "succeeded") return DEPLOY_STEPS.length;
  if (job || selected) return 2;
  return 1;
}

export function stepState(index: number, current: number): DeployStepState {
  if (index < current) return "done";
  return index === current ? "current" : "todo";
}
