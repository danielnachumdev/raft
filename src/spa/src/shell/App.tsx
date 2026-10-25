import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { Dashboard } from "./Dashboard";
import { AddServicePage } from "../deploy/AddServicePage";
import { DeployPage } from "../deploy/DeployPage";
import { FirewallSettingsPage } from "../firewall/FirewallSettingsPage";
import { AlertsSettingsPage } from "../alerts/AlertsSettingsPage";
import { InboxPage } from "../inbox/InboxPage";
import { NotificationsSettingsPage } from "../notifications/NotificationsSettingsPage";
import { SettingsPage } from "../settings/SettingsPage";
import { EventsPage } from "../events/EventsPage";
import { ServicePage } from "../service/ServicePage";
import { ToastHost } from "../chrome/ToastHost";

export function App() {
  return (
    <>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/add-service" element={<AddServicePage />} />
          <Route path="/deploy" element={<DeployPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route
            path="/settings/notifications"
            element={<NotificationsSettingsPage />}
          />
          <Route path="/settings/alerts" element={<AlertsSettingsPage />} />
          <Route
            path="/settings/edge-access"
            element={<FirewallSettingsPage />}
          />
          <Route path="/service/:service" element={<ServicePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <ToastHost />
    </>
  );
}
