/**
 * Who is signed in, app-wide. The session itself is an httpOnly cookie the
 * API owns; this just asks /auth/me once and caches the answer.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { api, type PortalId, type User } from "../api";
import { PORTALS } from "../components/PortalShell";

type AuthState = {
  user: User | null;
  ready: boolean;
  setUser: (user: User | null) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setUser((await api.auth.me()).user);
    } catch (err: any) {
      // Don't log out if it's just a network error or server timeout. Only log out on actual 401.
      if (err?.status === 401) {
        setUser(null);
      }
    } finally {
      setReady(true);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const handleFocus = () => void refresh();
    const handleVisibility = () => { if (document.visibilityState === "visible") void refresh(); };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [refresh]);

  const value = useMemo(() => ({ user, ready, setUser, refresh, logout }), [user, ready, refresh, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/**
 * Gate for a portal's private pages. No session → that portal's sign-in;
 * a session for a different portal → the same, never a silent pass-through.
 */
export function RequireAuth({ portal, children }: { portal: PortalId; children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <div className="page muted">Loading…</div>;
  if (!user || user.portal !== portal) {
    return <Navigate to={PORTALS[portal].login} replace state={{ from: location.pathname, wrongPortal: user?.portal ?? null }} />;
  }
  // Kaam (worker) onboarding gate: pending workers see a verification screen.
  if (portal === "kaam" && user.worker_status === "pending") {
    return <Navigate to="/kaam/verification" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
