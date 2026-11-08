import { runLogout, type LogoutHint } from "./useDashboardSession";

/** Account-menu control to end password / OAuth / external dashboard sessions. */
export function LogoutButton(props: {
  hint: LogoutHint;
  className?: string;
  id?: string;
}) {
  const classes = ["btn", "btn-sm", "btn-ghost", props.className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={classes}
      id={props.id ?? "dashboard-logout"}
      role="menuitem"
      onClick={() => void runLogout(props.hint)}
    >
      Log out
    </button>
  );
}
