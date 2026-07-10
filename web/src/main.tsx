import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/scrolly.css";
import "./styles/explore.css";
import "./styles/graph.css";
import { applyTheme, resolveInitialTheme } from "./theme";

applyTheme(resolveInitialTheme());

const root = document.getElementById("root");
if (!root) {
  throw new Error("Root element #root not found");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
