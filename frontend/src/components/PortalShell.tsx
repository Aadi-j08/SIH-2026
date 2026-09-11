import { useEffect, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { type PortalId } from "../api";
import { initials, useAuth } from "../lib/auth";
import { LogOut } from "./Icons";

export type { PortalId };

export type Portal = {
  name: string;
  hindi: string;
  tag: string;
  accent: string;
  who: string;
  blurb: string;
  cta: string;
  /** public landing page for this portal */
  landing: string;
  login: string;
  signup: string;
  /** first private page after sign-in */
  home: string;
};

export const PORTALS: Record<PortalId, Portal> = {
  ghar: {
    name: "Ghar", hindi: "घर", tag: "Home", accent: "#c65d26",
    who: "I need a worker",
    blurb: "Book in a minute, see who is coming and why, pay after the job.",
    cta: "Book a service",
    landing: "/ghar", login: "/ghar/login", signup: "/ghar/signup", home: "/ghar/home",
  },
  kaam: {
    name: "Kaam", hindi: "काम", tag: "Work", accent: "#25984d",
    who: "I am a worker",
    blurb: "Say when you’re free, in Hindi or English. Get jobs shared fairly. Count your days to benefits.",
    cta: "Open my work",
    landing: "/kaam", login: "/kaam/login", signup: "/kaam/signup", home: "/kaam/home",
  },
  sabha: {
    name: "Sabha", hindi: "सभा", tag: "Council", accent: "#5e78d9",
    who: "I run the cooperative",
    blurb: "Assign work with the engine’s reasons, watch every rupee split, see next week’s demand.",
    cta: "Open the dashboard",
    landing: "/sabha", login: "/sabha/login", signup: "/sabha/signup", home: "/sabha/home",
  },
};

export const PORTAL_ORDER: PortalId[] = ["ghar", "kaam", "sabha"];

export function BrandMark({ color = "#c65d26", size = 28 }: { color?: string; size?: number }) {
  return (
    <svg className="mark" width={size} height={size} viewBox="0 0 512 512" aria-hidden="true">
      <rect width="512" height="512" rx="112" fill={color} />
      <path d="M96 336c40-96 104-144 160-144s120 48 160 144" fill="none" stroke="#FCFAF6" strokeWidth="40" strokeLinecap="round" />
      <path d="M144 336v48M256 208v176M368 336v48" stroke="#FCFAF6" strokeWidth="32" strokeLinecap="round" />
    </svg>
  );
}

/** The brand name: "Sahakar" in Latin, "सेतु" in Devanagari — one word, two scripts. */
export function Wordmark({ children }: { children?: ReactNode }) {
  return (
    <span className="wordmark">
      <span className="wordmark-text">
        Sahakar<span className="hi setu">सेतु</span>
      </span>
      {children}
    </span>
  );
}

export function PortalTag({ portal, style }: { portal: PortalId; style?: React.CSSProperties }) {
  const p = PORTALS[portal];
  return (
    <span className={`portal-tag ${portal}`} style={style}>
      {p.name} · {p.tag}
    </span>
  );
}

/** Sets the browser theme colour to the portal accent while the portal is open. */
export function useThemeColor(color: string) {
  useEffect(() => {
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    const previous = meta?.content;
    if (meta) meta.content = color;
    return () => {
      if (meta && previous) meta.content = previous;
    };
  }, [color]);
}

/** The signed-in person: initials, and the only way out — sign out, back to this portal's landing page. */
export function UserMenu({ portal }: { portal: PortalId }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const signOut = async () => {
    await logout();
    navigate(PORTALS[portal].landing, { replace: true });
  };
  return (
    <div className="row" style={{ gap: 8 }}>
      <span className="avatar small-avatar" title={user.name} aria-label={user.name}>
        {initials(user.name)}
      </span>
      <button type="button" className="back" onClick={signOut}>
        <LogOut size={16} />
        <span className="hide-narrow">Sign out</span>
      </button>
    </div>
  );
}

/**
 * The frame every private portal page sits in: its own accent (via
 * data-portal), its tag beside the wordmark, and the signed-in person with a
 * sign-out — no link to any other portal, so each one reads as its own place.
 */
export default function PortalShell({ portal, children, sidebar }: { portal: PortalId; children: ReactNode; sidebar?: ReactNode }) {
  const p = PORTALS[portal];
  useThemeColor(p.accent);

  const topbar = (
    <header className="topbar">
      <Link to={p.home} className="brand">
        <BrandMark color={p.accent} />
        <Wordmark>
          <small>
            {p.name} · {p.tag}
          </small>
        </Wordmark>
      </Link>
      <div className="row" style={{ gap: 10 }}>
        <PortalTag portal={portal} />
        <UserMenu portal={portal} />
      </div>
    </header>
  );

  if (sidebar) {
    return (
      <div className="shell" data-portal={portal}>
        <div className="sabha-layout">
          {topbar}
          {sidebar}
          {children}
        </div>
      </div>
    );
  }
  return (
    <div className="shell" data-portal={portal}>
      {topbar}
      {children}
    </div>
  );
}
