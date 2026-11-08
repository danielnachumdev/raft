import { useEffect, useState } from "react";
import { detailFromBody, readJsonBody } from "../shared/api";

export type LogoutHint = {
  kind: string;
  path: string;
  next?: string;
};

type SessionPayload = {
  mode: string;
  logout: LogoutHint;
};

/** Dashboard session hint used by the account menu logout control. */
export function useDashboardSession(): LogoutHint | null {
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

  return hint;
}

/** End password / OAuth / external dashboard sessions. */
export async function runLogout(hint: LogoutHint): Promise<void> {
  if (hint.kind === "navigate") {
    window.location.assign(hint.path);
    return;
  }
  if (hint.kind === "post") {
    let next = hint.next || "/login";
    try {
      const res = await fetch(hint.path, {
        method: "POST",
        credentials: "same-origin",
      });
      const body = (await readJsonBody(res)) as { next?: string; detail?: string };
      if (!res.ok) {
        throw new Error(detailFromBody(body) || `logout ${res.status}`);
      }
      if (typeof body?.next === "string" && body.next) {
        next = body.next;
      }
    } catch {
      /* still leave the session UI */
    }
    window.location.assign(next);
  }
}
