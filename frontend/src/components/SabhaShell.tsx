/**
 * The Sabha portal frame: sidebar navigation, the cooperative header
 * (who we are, how many of us, what needs attention), and the signed-in
 * council member. Every Sabha page renders inside it and reads the shared
 * overview through useSabha().
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactElement, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { api, errorMessage, type Overview } from "../api";
import { initials, useAuth } from "../lib/auth";
import { useLive } from "../lib/live";
import {
  Bell, Building, CalendarIcon, ChevronDown, Coins, Home, LayoutGrid, LogOut, Megaphone, Receipt, Refresh, Scale, Settings, ShieldCheck, TrendingUp, Users,
} from "./Icons";
import { BrandMark, PORTALS, useThemeColor, Wordmark } from "./PortalShell";

type SabhaState = {
  overview: Overview | null;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
  /** true while the server-sent events stream is connected */
  live: boolean;
};

const SabhaContext = createContext<SabhaState | null>(null);

export function useSabha(): SabhaState {
  const ctx = useContext(SabhaContext);
  if (!ctx) throw new Error("useSabha must be used inside SabhaShell");
  return ctx;
}

const NAV: { to: string; label: string; icon: (p: { size?: number }) => ReactElement; end?: boolean }[] = [
  { to: "/sabha/home", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/sabha/demands", label: "Demands", icon: CalendarIcon },
  { to: "/sabha/workers", label: "Workers", icon: Users },
  { to: "/sabha/customers", label: "Customers", icon: Home },
  { to: "/sabha/payments", label: "Payments", icon: Receipt },
  { to: "/sabha/fund", label: "Cooperative Fund", icon: Coins },
  { to: "/sabha/disputes", label: "Disputes", icon: Scale },
  { to: "/sabha/reports", label: "Reports & Insights", icon: TrendingUp },
];
const NAV_2: typeof NAV = [
  { to: "/sabha/announcements", label: "Announcements", icon: Megaphone },
  { to: "/sabha/profile", label: "Sabha Profile", icon: Building },
  { to: "/sabha/settings", label: "Settings", icon: Settings },
];

function NavItems({ items, onPick }: { items: typeof NAV; onPick?: () => void }) {
  return (
    <>
      {items.map(({ to, label, icon: IconFor, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : undefined)} onClick={onPick}>
          <IconFor size={20} />
          {label}
        </NavLink>
      ))}
    </>
  );
}

export default function SabhaShell({ children }: { children: ReactNode }) {
  const p = PORTALS.sabha;
  useThemeColor(p.accent);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [menu, setMenu] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setOverview(await api.admin.overview());
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // live: every write anywhere in the cooperative refreshes the overview; the timer is only a safety net
  const { live } = useLive(() => void reload());
  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => void reload(), live ? 120000 : 30000);
    return () => window.clearInterval(timer);
  }, [reload, live]);

  const value = useMemo(() => ({ overview, error, loading, reload, live }), [overview, error, loading, reload, live]);
  const coop = overview?.cooperative;
  const alerts = overview?.attention.filter((a) => a.level !== "green").length ?? 0;

  const signOut = async () => {
    await logout();
    navigate(p.landing, { replace: true });
  };

  return (
    <SabhaContext.Provider value={value}>
      <div className="shell" data-portal="sabha">
        <div className="sabha-layout">
          <aside className="sidebar">
            <Link to="/sabha/home" className="brand">
              <BrandMark color={p.accent} />
              <Wordmark>
                <small>Sabha · Council</small>
              </Wordmark>
            </Link>
            <nav aria-label="Sabha">
              <NavItems items={NAV} />
              <div className="sidebar-gap" />
              <NavItems items={NAV_2} />
            </nav>
            <div className="grow" />
            {user && (
              <div className="row" style={{ gap: 10 }}>
                <span className="avatar small-avatar">{initials(user.name)}</span>
                <div className="stack grow" style={{ gap: 0 }}>
                  <div className="small" style={{ fontWeight: 700 }}>{user.name}</div>
                  <div className="tiny muted">{user.role ?? "Council member"}</div>
                </div>
                <button type="button" className="back" onClick={signOut} aria-label="Sign out">
                  <LogOut size={16} />
                </button>
              </div>
            )}
          </aside>

          <div className="sabha-main">
            <header className="sabha-header">
              <div className="row" style={{ gap: 12, minWidth: 0 }}>
                <button type="button" className="icon-btn menu-btn" onClick={() => setMenu((m) => !m)} aria-label="Menu" aria-expanded={menu}>
                  <LayoutGrid size={22} />
                </button>
                <div className="stack" style={{ gap: 2, minWidth: 0 }}>
                  <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
                    <span className="display sabha-title">
                      SABHA <span className="muted" style={{ fontWeight: 500 }}>—</span> {coop?.short_name ?? "Cooperative"}
                    </span>
                    {coop?.verified && (
                      <span className="pill green" style={{ gap: 5 }}>
                        <ShieldCheck size={13} />
                        Verified Cooperative
                      </span>
                    )}
                  </div>
                  <div className="small muted hide-narrow">
                    {coop ? `${coop.members} Members · ${coop.active_workers} Active Workers · ${coop.categories} Service Categories` : "Loading the cooperative…"}
                  </div>
                </div>
              </div>
              <div className="row" style={{ gap: 6 }}>
                <span className={`pill hide-narrow ${live ? "green" : "grey"}`} title={live ? "Updates arrive the moment something changes" : "Live stream down; polling every 30 s"} style={{ gap: 6 }}>
                  <span className="live-dot" aria-hidden="true" />
                  {live ? "Live" : "Polling"}
                </span>
                <button type="button" className="btn outline small hide-narrow" onClick={() => void reload()} disabled={loading}>
                  <Refresh size={16} />
                  {loading ? "Refreshing…" : "Refresh"}
                </button>
                <Link to="/sabha/home#attention" className="icon-btn" aria-label={`${alerts} items need attention`} title="Needs attention">
                  <Bell size={20} />
                  {alerts > 0 && <span className="dot-badge">{alerts}</span>}
                </Link>
                <Link to="/sabha/settings" className="icon-btn" aria-label="Settings" title="Settings">
                  <Settings size={20} />
                </Link>
                {user && (
                  <details className="user-menu">
                    <summary>
                      <span className="avatar small-avatar">{initials(user.name)}</span>
                      <span className="hide-narrow small" style={{ fontWeight: 700 }}>
                        {user.role ? `Sabha ${user.role}` : "Sabha Admin"}
                      </span>
                      <ChevronDown size={16} />
                    </summary>
                    <div className="user-menu-panel">
                      <div className="stack" style={{ gap: 2, padding: "6px 10px 10px" }}>
                        <div style={{ fontWeight: 700 }}>{user.name}</div>
                        <div className="tiny muted">+91 {user.phone}</div>
                      </div>
                      <Link to="/sabha/profile">Sabha profile</Link>
                      <Link to="/sabha/settings">Settings</Link>
                      <button type="button" onClick={signOut}>
                        <LogOut size={16} />
                        Sign out
                      </button>
                    </div>
                  </details>
                )}
              </div>
            </header>

            {menu && (
              <nav className="sabha-drawer" aria-label="Sabha">
                <NavItems items={[...NAV, ...NAV_2]} onPick={() => setMenu(false)} />
              </nav>
            )}

            {children}
          </div>
        </div>
      </div>
    </SabhaContext.Provider>
  );
}
