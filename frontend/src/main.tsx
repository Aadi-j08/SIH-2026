import { Component, StrictMode, type ErrorInfo, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./styles.css";

registerSW({ immediate: true });

class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Keep the UI usable even when a malformed API response breaks one view.
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="page">
          <div className="notice error">Something went wrong while loading this page.</div>
          <button type="button" className="btn primary" onClick={() => window.location.reload()}>
            Reload
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppErrorBoundary>
      <BrowserRouter basename="/app">
        <App />
      </BrowserRouter>
    </AppErrorBoundary>
  </StrictMode>,
);
