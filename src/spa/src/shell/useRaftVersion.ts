import { useEffect, useState } from "react";
import type { RaftVersion } from "../shared/api/index.ts";
import { peekStatus, refreshStatus } from "../shared/dashboardCache";

/** Installed raft version from status cache / one-shot refresh for shell chrome. */
export function useRaftVersion(): RaftVersion | null {
  const [version, setVersion] = useState<RaftVersion | null>(
    () => peekStatus()?.version ?? null,
  );

  useEffect(() => {
    let cancelled = false;
    void refreshStatus()
      .then((payload) => {
        if (!cancelled && payload.version) {
          setVersion(payload.version);
        }
      })
      .catch(() => {
        /* keep cached / empty — chrome stays quiet */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return version;
}
