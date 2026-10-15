import { useState } from "react";
import { ConfirmPopup } from "../../../chrome/ConfirmPopup";
import {
  createDashboard,
  deleteDashboard,
  newId,
  renameDashboard,
  restoreDefaultPanels,
  setActiveDashboard,
  suggestDashboardName,
} from "../model/index.ts";
import { DashboardNameModal } from "./DashboardNameModal";
import { MenuButton } from "./MenuButton";
import type { DashboardStoreApi } from "./useDashboardStore";

type Dialog = "new" | "rename" | "delete" | "restore" | null;

/** Dashboard switcher + new / rename / restore defaults / delete. */
export function DashboardPicker(props: { api: DashboardStoreApi }) {
  const { api } = props;
  const [dialog, setDialog] = useState<Dialog>(null);
  const close = () => setDialog(null);
  const current = api.dashboard;
  const switchTo = (id: string) => {
    api.dismissUndo();
    api.setStore((s) => setActiveDashboard(s, id));
  };

  return (
    <div className="trends-dash-picker">
      <label className="trends-field">
        <span>Dashboard</span>
        <select
          value={current.id}
          onChange={(e) => switchTo(e.target.value)}
          aria-label="Dashboard"
        >
          {api.store.dashboards.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </label>
      <MenuButton
        label="Dashboard options"
        items={[
          { id: "new", label: "New dashboard…", onSelect: () => setDialog("new") },
          { id: "rename", label: "Rename…", onSelect: () => setDialog("rename") },
          {
            id: "restore",
            label: "Restore default graphs…",
            onSelect: () => setDialog("restore"),
          },
          {
            id: "delete",
            label: "Delete dashboard…",
            danger: true,
            separatorBefore: true,
            onSelect: () => setDialog("delete"),
          },
        ]}
      />
      <DashboardNameModal
        open={dialog === "new"}
        title="New dashboard"
        initialName={suggestDashboardName(api.store)}
        confirmLabel="Create"
        onCancel={close}
        onConfirm={(name) => {
          api.dismissUndo();
          api.setStore((s) => createDashboard(s, name, newId("dash")));
          close();
        }}
      />
      <DashboardNameModal
        open={dialog === "rename"}
        title="Rename dashboard"
        initialName={current.name}
        confirmLabel="Rename"
        onCancel={close}
        onConfirm={(name) => {
          api.setStore((s) => renameDashboard(s, current.id, name));
          close();
        }}
      />
      <ConfirmPopup
        open={dialog === "restore"}
        title="Restore default graphs"
        message={restoreMessage(current.name, current.panels.length)}
        confirmLabel="Restore defaults"
        onCancel={close}
        onConfirm={() => {
          api.dismissUndo();
          api.edit(restoreDefaultPanels);
          close();
        }}
      />
      <ConfirmPopup
        open={dialog === "delete"}
        title="Delete dashboard"
        message={`Delete “${current.name}”? This only removes it from this browser.`}
        confirmLabel="Delete"
        danger
        onCancel={close}
        onConfirm={() => {
          api.dismissUndo();
          api.setStore((s) => deleteDashboard(s, current.id));
          close();
        }}
      />
    </div>
  );
}

function restoreMessage(name: string, count: number): string {
  const defaults =
    "the default CPU, memory, request rate, latency, errors and network graphs";
  if (count === 0) return `Add ${defaults} to “${name}”?`;
  const graphs = count === 1 ? "1 graph" : `${count} graphs`;
  return `Replace the ${graphs} on “${name}” with ${defaults}?`;
}
