import { useEffect, useState } from "react";
import type { StatusPayload } from "../../shared/api/index.ts";
import { peekStatus, refreshStatus } from "../../shared/dashboardCache";
import { aboutFactRows } from "../aboutFacts";
import { SectionCard } from "../SectionCard";

/** Read-only machine + install facts from ``/api/status`` (not settings.yaml). */
export function AboutSection() {
  const [payload, setPayload] = useState<StatusPayload | null>(() => peekStatus());

  useEffect(() => {
    let cancelled = false;
    void refreshStatus()
      .then((next) => {
        if (!cancelled) setPayload(next);
      })
      .catch(() => {
        /* keep cached snapshot if any */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <SectionCard
      id="settings-about"
      title="About"
      hint="Installed raft version and this machine's identity. Read-only — not part of settings.yaml."
    >
      <dl className="settings-about-facts" id="settings-about-facts">
        {aboutFactRows(payload?.host, payload?.version).map((row) => (
          <div key={row.label} className="settings-about-row">
            <dt>{row.label}</dt>
            <dd>{row.mono ? <code>{row.value}</code> : row.value}</dd>
          </div>
        ))}
      </dl>
    </SectionCard>
  );
}
