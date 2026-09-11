import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { api, errorMessage, type PortalId } from "../api";
import { AuthShell, Divider, Field, PasswordField, PhoneField } from "../components/AuthForm";
import { ArrowRight, Info } from "../components/Icons";
import { PORTALS, PORTAL_ORDER } from "../components/PortalShell";
import { useAuth } from "../lib/auth";

/** Who each portal's sign-in is for, for the "you may be in the wrong place" line. */
const WHO: Record<PortalId, string> = { ghar: "Households", kaam: "Workers", sabha: "Council members" };

const COPY: Record<PortalId, { audience: string; title: string; hindi: string; newHere: string; create: string; note: string }> = {
  ghar: {
    audience: "For households", title: "Welcome back to Ghar.", hindi: "घर में आपका स्वागत है",
    newHere: "New to Ghar?", create: "Create a Ghar account",
    note: "This sign-in is for households.",
  },
  kaam: {
    audience: "For workers", title: "Welcome back to Kaam.", hindi: "काम में आपका स्वागत है",
    newHere: "New to Kaam?", create: "Join as a worker",
    note: "This sign-in is for workers of the cooperative.",
  },
  sabha: {
    audience: "Council members", title: "Welcome back to Sabha.", hindi: "सभा में आपका स्वागत है",
    newHere: "Not registered yet?", create: "I have a council code",
    note: "This sign-in is for the cooperative's council.",
  },
};

export default function SignIn({ portal }: { portal: PortalId }) {
  const p = PORTALS[portal];
  const copy = COPY[portal];
  const { user, ready, setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as { from?: string; wrongPortal?: PortalId | null };

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (ready && user?.portal === portal) return <Navigate to={state.from ?? p.home} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { user: signedIn } = await api.auth.login(portal, phone, password);
      setUser(signedIn);
      navigate(state.from ?? p.home, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const others = PORTAL_ORDER.filter((id) => id !== portal);

  return (
    <AuthShell portal={portal}>
      <form className="stack-lg" onSubmit={submit}>
        <div className="stack" style={{ gap: 8, paddingTop: 12 }}>
          <div className="label" style={{ color: "var(--accent-d)" }}>{copy.audience}</div>
          <h1 style={{ fontSize: 32 }}>{copy.title}</h1>
          <div className="hi" style={{ fontSize: 16, color: "var(--ink-2)" }}>{copy.hindi}</div>
        </div>

        {state.wrongPortal && (
          <div className="notice info row" style={{ gap: 10, alignItems: "flex-start" }}>
            <Info size={18} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              You are signed in to <strong>{PORTALS[state.wrongPortal].name}</strong>. {p.name} keeps its own accounts — sign in here with a {p.name} account.
            </span>
          </div>
        )}

        <Field label="Mobile number">
          <PhoneField value={phone} onChange={setPhone} autoFocus />
        </Field>
        <Field label="Password">
          <PasswordField value={password} onChange={setPassword} />
        </Field>

        {error && <div className="notice error">{error}</div>}

        <button type="submit" className="btn primary block" disabled={busy || !phone.trim() || !password}>
          {busy ? "Signing in…" : "Sign in"}
          {!busy && <ArrowRight size={20} />}
        </button>

        <Divider text={copy.newHere.toUpperCase()} />
        <Link to={p.signup} className="btn outline block" style={{ minHeight: 50, fontSize: 15, color: "var(--ink)" }}>
          {copy.create}
        </Link>

        <div className="notice info row" style={{ gap: 10, alignItems: "flex-start", marginTop: 8 }}>
          <Info size={16} style={{ flexShrink: 0, marginTop: 2, color: "var(--ink-3)" }} />
          <span className="tiny">
            {copy.note}{" "}
            {others.map((id, i) => (
              <span key={id}>
                {i === 0 ? "" : " · "}
                {WHO[id]} sign in at{" "}
                <Link to={PORTALS[id].login} style={{ fontWeight: 700 }}>
                  {PORTALS[id].name}
                </Link>
              </span>
            ))}
          </span>
        </div>
      </form>
    </AuthShell>
  );
}
