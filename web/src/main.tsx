import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { HostDemo } from "./host/HostDemo";
import LabChat from "./lab/LabChat";
import "./index.css";

try {
  sessionStorage.removeItem("kori.reload");       // the app loaded: forget earlier failed tries (see index.html)
} catch {
  /* private mode */
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {location.pathname === "/host" ? <HostDemo /> : location.pathname === "/lab" ? <LabChat /> : <App />}
  </StrictMode>,
);
