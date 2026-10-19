import { useEffect, useState } from "react";
import { ConfirmPopup } from "../../chrome/ConfirmPopup";
import { toast } from "../../chrome/toast";
import {
  applyInspectionFirewallRule,
  fetchFirewallServices,
  fetchInspectionFirewallDraft,
  removeInspectionFirewallRule,
  type FirewallRule,
  type FirewallServiceOption,
} from "../../firewall/firewallApi";
import {
  FirewallRuleFormModal,
  type FirewallRuleFormSubmit,
} from "../../firewall/FirewallRuleFormModal";

type Props = {
  clientIp: string;
  /** App name (firewall service scope), not Compose id. */
  appName: string | null;
};

/** Add / update / remove ordered firewall rules for a request client IP. */
export function InspectionFirewallActions(props: Props) {
  const [services, setServices] = useState<FirewallServiceOption[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [formBusy, setFormBusy] = useState(false);
  const [draft, setDraft] = useState<FirewallRule | null>(null);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [matchCount, setMatchCount] = useState(0);
  const [removeOpen, setRemoveOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetchFirewallServices()
      .then((rows) => {
        if (!cancelled) setServices(rows);
      })
      .catch(() => {
        if (!cancelled) setServices([{ name: "any", label: "Any (edge-wide)" }]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function openAdd() {
    try {
      const payload = await fetchInspectionFirewallDraft({
        clientIp: props.clientIp,
        service: props.appName ?? undefined,
        action: "deny",
      });
      const existing = payload.matches[0] ?? null;
      setMatchCount(payload.matches.length);
      setMode(existing ? "edit" : "create");
      setDraft(existing ?? payload.rule);
      setFormOpen(true);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to draft rule");
    }
  }

  async function openRemove() {
    try {
      const payload = await fetchInspectionFirewallDraft({
        clientIp: props.clientIp,
        service: props.appName ?? undefined,
      });
      if (payload.matches.length === 0) {
        toast.bad("No firewall rule matches this client host CIDR");
        return;
      }
      setMatchCount(payload.matches.length);
      setRemoveOpen(true);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to look up rules");
    }
  }

  async function onSubmit(body: FirewallRuleFormSubmit) {
    setFormBusy(true);
    try {
      await applyInspectionFirewallRule(body);
      setFormOpen(false);
      setDraft(null);
      toast.good(
        "Firewall rule applied at top of table (gate nginx reload)",
      );
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to apply rule");
    } finally {
      setFormBusy(false);
    }
  }

  async function onRemove() {
    try {
      await removeInspectionFirewallRule({ clientIp: props.clientIp });
      setRemoveOpen(false);
      setMatchCount(0);
      toast.good("Matching firewall rule removed (gate nginx reload)");
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "Failed to remove rule");
    }
  }

  return (
    <div className="http-requests-fw">
      <button
        type="button"
        className="btn btn-sm"
        title="Add or update a firewall rule for this client IP"
        onClick={() => void openAdd()}
      >
        Add rule
      </button>
      <button
        type="button"
        className="btn btn-sm btn-danger"
        title="Remove matching host CIDR firewall rule"
        onClick={() => void openRemove()}
      >
        Remove
      </button>
      <FirewallRuleFormModal
        open={formOpen}
        mode={mode}
        rule={draft}
        services={services}
        busy={formBusy}
        onClose={() => {
          if (!formBusy) {
            setFormOpen(false);
            setDraft(null);
          }
        }}
        onSubmit={(body) => void onSubmit(body)}
      />
      <ConfirmPopup
        open={removeOpen}
        title="Remove firewall rule"
        message={`Remove ${matchCount} ordered firewall rule(s) for ${props.clientIp} (host /32 or /128) and reload gate nginx?`}
        confirmLabel="Remove"
        danger
        onConfirm={() => onRemove()}
        onCancel={() => setRemoveOpen(false)}
      />
    </div>
  );
}
