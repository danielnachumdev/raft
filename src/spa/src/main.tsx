import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { applyTheme, resolveTheme } from "./shared/chrome/theme";
import { RbacProvider } from "./features/rbac";
import { App } from "./app/App";
import "./styles.css";

applyTheme(resolveTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <RbacProvider>
        <App />
      </RbacProvider>
    </BrowserRouter>
  </StrictMode>,
);
