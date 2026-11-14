import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

try {
  sessionStorage.removeItem("kori.reload");       // the app loaded: forget earlier failed tries (see index.html)
} catch {
  /* private mode */
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
