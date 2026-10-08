import { Navigate, Route, Routes } from "react-router-dom";
import { Dashboard } from "./Dashboard";
import { DeployPage } from "../deploy/DeployPage";
import { ServicePage } from "../service/ServicePage";
import { ToastHost } from "../chrome/ToastHost";

export function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/deploy" element={<DeployPage />} />
        <Route path="/service/:service" element={<ServicePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastHost />
    </>
  );
}
