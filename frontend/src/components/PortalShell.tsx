import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ArrowLeft } from "./Icons";

export type PortalId = "ghar" | "kaam" | "sabha";

export const PORTALS: Record<PortalId, { name: string; hindi: string; tag: string; path: string; accent: string; who: string; blurb: string; cta: string }> = {
  ghar: { name: "Ghar", hindi: "घर", tag: "Home", path: "/customer", accent: "#c65d26", who: "I need a worker", blurb: "Book in a minute, see who is coming and why, pay after the job.", cta: "Book a service" },
  kaam: { name: "Kaam", hindi: "काम", tag: "Work", path: "/worker", accent: "#25984d", who: "I am a worker", blurb: "Say when you’re free, in Hindi or English. Get jobs shared fairly. Count your days to benefits.", cta: "Open my work" },
  sabha: { name: "Sabha", hindi: "सभा", tag: "Council", path: "/admin", accent: "#5e78d9", who: "I run the cooperative", blurb: "Assign work with the engine’s reasons, watch every rupee split, see next week’s demand.", cta: "Open the dashboard" },
};

export function BrandMark({ color = "#c65d26", size = 28 }: { color?: string; size?: number }) {
  return (
    <svg className="mark" width={size} height={size} viewBox="0 0 512 512" aria-hidden="true">
      <rect width="512" height="512" rx="112" fill={color} />
      <path d="M96 336c40-96 104-144 160-144s120 48 160 144" fill="none" stroke="#FCFAF6" strokeWidth="40" strokeLinecap="round" />
      <path d="M144 336v48M256 208v176M368 336v48" stroke="#FCFAF6" strokeWidth="32" strokeLinecap="round" />
    </svg>
  );
}

export function PortalTag({ portal }: { portal: PortalId }) {
  const p = PORTALS[portal];
  return (
    <span className={`portal-tag ${portal}`}>
      {p.name} · {p.tag}
    </span>
  );
}

/** Sets the browser theme colour to the portal accent while the portal is open. */
function useThemeColor(color: string) {
  useEffect(() => {
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    const previous = meta?.content;
    if (meta) meta.content = color;
    return () => {
      if (meta && previous) meta.content = previous;
    };
  }, [color]);
}

/**
 * The frame every portal page sits in: its own accent (via data-portal),
 * its tag beside the wordmark, and a way back to the landing page instead
 * of a role switcher — so each portal reads as its own place.
 */
export default function PortalShell({ portal, children, sidebar }: { portal: PortalId; children: ReactNode; sidebar?: ReactNode }) {
  const p = PORTALS[portal];
  useThemeColor(p.accent);

  const topbar = (
    <header className="topbar">
      <Link to={p.path} className="brand">
        <BrandMark color={p.accent} />
        <span className="wordmark">
          SahakarSetu
          <small>
            {p.name} · {p.tag}
          </small>
        </span>
      </Link>
      <div className="row" style={{ gap: 10 }}>
        <PortalTag portal={portal} />
        <Link to="/" className="back" aria-label="Back to the SahakarSetu home page">
          <ArrowLeft size={16} />
          <span className="hide-narrow">All portals</span>
        </Link>
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
