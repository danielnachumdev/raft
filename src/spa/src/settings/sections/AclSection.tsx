import { Link } from "react-router-dom";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument } from "../settingsApi";

/** Legacy flat ACL — editable for migrate, prefer ordered firewall. */
export function AclSection(props: {
  value: SettingsDocument["acl"];
  onChange: (next: SettingsDocument["acl"]) => void;
}) {
  const gate = props.value.gate;
  const setMode = (mode: string) =>
    props.onChange({ gate: { ...gate, mode } });
  return (
    <SectionCard
      id="settings-acl"
      title="ACL (legacy)"
      hint={
        <>
          Flat <code>acl.gate</code> is retired as an operator path. Prefer{" "}
          <Link to="/settings/edge-access">Settings → Firewall</Link>. Leftover
          ACL migrates into the firewall editor until Save.
        </>
      }
    >
      <label className="field" htmlFor="acl-mode">
        Gate mode
        <select
          id="acl-mode"
          value={gate.mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="off">off</option>
          <option value="whitelist">whitelist</option>
          <option value="blacklist">blacklist</option>
        </select>
      </label>
      <p className="muted" id="settings-acl-count">
        {gate.entries.length} entr{gate.entries.length === 1 ? "y" : "ies"}{" "}
        (edit CIDRs via Firewall after migrate).
      </p>
      {gate.entries.length ? (
        <ul className="settings-acl-list">
          {gate.entries.map((entry) => (
            <li key={entry.id}>
              <code>{entry.id}</code> {entry.cidr}
              {entry.comment ? (
                <span className="muted"> — {entry.comment}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </SectionCard>
  );
}
