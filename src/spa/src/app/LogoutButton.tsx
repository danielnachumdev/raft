import { useEffect, useState } from "react";
import { detailFromBody, readJsonBody } from "../shared/api";

type LogoutHint = {
  kind: string;
  path: string;
  next?: string;
};

type SessionPayload = {
  mode: string;
  logout: LogoutHint;
};

/** Top-bar control to end password / OAuth / external dashboard sessions. */
export function LogoutButton(props: { className?: string; id?: string }) {
  const [hint, setHint] = useState<LogoutHint | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/dashboard/session", {
          credentials: "same-origin",
        });
        if (!res.ok) return;
        const body = (await readJsonBody(res)) as SessionPayload;
        if (cancelled) return;
        if (body?.mode && body.mode !== "none" && body.logout?.kind !== "none") {
          setHint(body.logout);
        }
      } catch {
        /* localhost / auth none — no logout control */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!hint) return null;

  const classes = ["btn", "btn-sm", "btn-ghost", props.className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={classes}
      id={props.id ?? "dashboard-logout"}
      onClick={() => void runLogout(hint)}
    >
      Log out
    </button>
  );
}

async function runLogout(hint: LogoutHint): Promise<void> {
  if (hint.kind === "navigate") {
    window.location.assign(hint.path);
    return;
  }
  if (hint.kind === "post") {
    try {
      const res = await fetch(hint.path, {
        method: "POST",
        credentials: "same-origin",
      });
      if (!res.ok) {
        const body = await readJsonBody(res);
        throw new Error(detailFromBody(body) || `logout ${res.status}`);
      }
    } catch {
      /* still leave the session UI */
    }
    window.location.assign(hint.next || "/login");
  }
}
