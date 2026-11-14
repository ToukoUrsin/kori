import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { HostDemo } from "./host/HostDemo";
import LabChat from "./lab/LabChat";
import "./index.css";

// `/lab` is the app with the chat open inside the phone; `/lab?dev=1` is the work view for technical readers.
// `?coach=old` keeps the old pages as they were.
const q = new URLSearchParams(location.search);
const labPage = location.pathname === "/lab" && (q.get("dev") === "1" || q.get("coach") === "old");

try {
  sessionStorage.removeItem("kori.reload");       // the app loaded: forget earlier failed tries (see index.html)
} catch {
  /* private mode */
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {location.pathname === "/host" ? <HostDemo /> : labPage ? <LabChat /> : <App />}
  </StrictMode>,
);
