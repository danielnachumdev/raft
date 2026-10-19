import { SectionCard } from "../SectionCard";
import { PurgeButton } from "../PurgeButton";

/** Host storage optimization — not part of settings.yaml. */
export function StorageSection() {
  return (
    <SectionCard
      id="settings-storage"
      title="Storage"
      hint="Cleanup actions that free Docker disk on this host. They do not change settings.yaml."
    >
      <div className="settings-storage-block">
        <h3 className="settings-storage-title">Purge unused images</h3>
        <p className="muted settings-storage-copy">
          Removes Docker images not used by any container and unused build
          cache. Images still attached to running or stopped containers are
          kept. App volumes and secrets under{" "}
          <code>~/.raft/</code> are not touched. Same as{" "}
          <code>raft purge</code>.
        </p>
        <PurgeButton />
      </div>
    </SectionCard>
  );
}
