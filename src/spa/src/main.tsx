import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { applyTheme, resolveTheme } from "./chrome/theme";
import { RbacProvider } from "./rbac";
import { App } from "./shell/App";
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
