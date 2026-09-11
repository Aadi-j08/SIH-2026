/**
 * Pieces shared by the sign-in and sign-up screens: the portal-branded top
 * bar, a phone field with the +91 adornment, a password field with show/hide.
 */
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { type PortalId } from "../api";
import { ArrowLeft, Eye, EyeOff } from "./Icons";
import { BrandMark, PORTALS, PortalTag, useThemeColor } from "./PortalShell";

/** Public (signed-out) frame for a portal's auth screens: brand + tag, nothing else. */
export function AuthShell({ portal, children, wide = false }: { portal: PortalId; children: ReactNode; wide?: boolean }) {
  const p = PORTALS[portal];
  useThemeColor(p.accent);
  return (
    <div className="shell" data-portal={portal}>
      <header className="topbar">
        <Link to={p.landing} className="brand">
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
          <Link to="/" className="back" aria-label="SahakarSetu home">
            <ArrowLeft size={16} />
            <span className="hide-narrow">Home</span>
          </Link>
        </div>
      </header>
      <main className={wide ? "page auth-wide" : "page"}>{children}</main>
    </div>
  );
}

export function Field({ label, hint, children, trailing }: { label: string; hint?: string; children: ReactNode; trailing?: ReactNode }) {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row between">
        <span className="label">{label}</span>
        {trailing}
      </div>
      {children}
      {hint && <div className="tiny muted">{hint}</div>}
    </div>
  );
}

export function PhoneField({ value, onChange, autoFocus = false }: { value: string; onChange: (v: string) => void; autoFocus?: boolean }) {
  return (
    <label className="field">
      <span className="adorn" aria-hidden="true">
        +91
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="98765 43210"
        inputMode="tel"
        autoComplete="tel-national"
        maxLength={20}
        required
        autoFocus={autoFocus}
        aria-label="Mobile number"
      />
    </label>
  );
}

export function PasswordField({ value, onChange, placeholder = "Password", autoComplete = "current-password", minLength = 1 }: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: "current-password" | "new-password";
  minLength?: number;
}) {
  const [shown, setShown] = useState(false);
  return (
    <label className="field">
      <input
        type={shown ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        minLength={minLength}
        maxLength={200}
        required
        aria-label="Password"
      />
      <button type="button" className="icon-btn" onClick={() => setShown((s) => !s)} aria-label={shown ? "Hide password" : "Show password"}>
        {shown ? <EyeOff size={20} /> : <Eye size={20} />}
      </button>
    </label>
  );
}

export function Divider({ text }: { text: string }) {
  return (
    <div className="row" style={{ gap: 12 }}>
      <span className="divider grow" />
      <span className="tiny" style={{ fontWeight: 700, color: "var(--ink-3)", letterSpacing: "0.06em" }}>
        {text}
      </span>
      <span className="divider grow" />
    </div>
  );
}
