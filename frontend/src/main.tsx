import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AppShellProvider } from "./context/AppShellContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <AppShellProvider>
      <App />
    </AppShellProvider>
  </BrowserRouter>,
);
