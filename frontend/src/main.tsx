import { Component, StrictMode, type ErrorInfo, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./styles.css";

registerSW({ immediate: true });

// ── Phase H: PWA A2HS (Add to Home Screen) install prompt capture ─────────
type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};
let deferredPrompt: InstallEvent | null = null;
const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches || (window.navigator as any).standalone === true;

window.addEventListener(
  "beforeinstallprompt",
  (e: Event) => {
    const ev = e as InstallEvent;
    ev.preventDefault();
    deferredPrompt = ev;
    (window as any).__sahakarsetuInstallable = true;
  },
  { passive: true },
);
if (isStandalone()) {
  (window as any).__sahakarsetuInstalled = true;
}
export async function triggerInstall(): Promise<boolean> {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    deferredPrompt = null;
    return choice.outcome === "accepted";
  }
  return false;
}
export function installable(): boolean {
  return (window as any).__sahakarsetuInstallable === true;
}


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

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppErrorBoundary>
      <BrowserRouter basename={basePath}>
        <App />
      </BrowserRouter>
    </AppErrorBoundary>
  </StrictMode>,
);
