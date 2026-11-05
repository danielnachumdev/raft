import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { Dashboard } from "./Dashboard";
import { AddServicePage } from "../deploy/AddServicePage";
import { DeployPage } from "../deploy/DeployPage";
import { FirewallSettingsPage } from "../firewall/FirewallSettingsPage";
import { AlertsSettingsPage } from "../alerts/AlertsSettingsPage";
import { InboxPage } from "../inbox/InboxPage";
import { NotificationsSettingsPage } from "../notifications/NotificationsSettingsPage";
import { ForbiddenPage, RbacSettingsPage, RequirePermission } from "../rbac";
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
          <Route
            path="/events"
            element={
              <RequirePermission permission="events:read">
                <EventsPage />
              </RequirePermission>
            }
          />
          <Route path="/inbox" element={<InboxPage />} />
          <Route
            path="/settings"
            element={
              <RequirePermission permission="settings:read">
                <SettingsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/settings/notifications"
            element={
              <RequirePermission permission="notifications:read">
                <NotificationsSettingsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/settings/alerts"
            element={
              <RequirePermission permission="alerts:read">
                <AlertsSettingsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/settings/edge-access"
            element={
              <RequirePermission permission="firewall:read">
                <FirewallSettingsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/settings/rbac"
            element={
              <RequirePermission permission="rbac:read">
                <RbacSettingsPage />
              </RequirePermission>
            }
          />
          <Route path="/service/:service" element={<ServicePage />} />
          <Route path="/forbidden" element={<ForbiddenPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <ToastHost />
    </>
  );
}
