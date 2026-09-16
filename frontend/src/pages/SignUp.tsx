import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { api, errorMessage, titleCase, TRADES, type PortalId, type SignupBody } from "../api";
import { AuthShell, Field, PasswordField, PhoneField } from "../components/AuthForm";
import { ArrowRight, Check, ChevronDown, Locate, Lock, Pin, TRADE_ICONS } from "../components/Icons";
import { BrandMark, PORTALS, PortalTag, Wordmark } from "../components/PortalShell";
import { useAuth } from "../lib/auth";

const LANGUAGES: { code: string; label: string; hi?: boolean }[] = [
  { code: "hi", label: "हिंदी", hi: true },
  { code: "en", label: "English" },
  { code: "mr", label: "मराठी", hi: true },
];

const SABHA_ROLES = ["Secretary", "President", "Treasurer", "Member"];

export default function SignUp({ portal }: { portal: PortalId }) {
  const p = PORTALS[portal];
  const { user, ready, setUser } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [locality, setLocality] = useState("");
  const [trade, setTrade] = useState<string>("plumbing");
  const [languages, setLanguages] = useState<string[]>(["hi"]);
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [role, setRole] = useState(SABHA_ROLES[0]);
  const [councilCode, setCouncilCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (ready && user?.portal === portal) return <Navigate to={p.home} replace />;

  const useGps = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        setLocating(false);
      },
      () => setLocating(false),
      { timeout: 8000 },
    );
  };

  const toggleLanguage = (code: string) =>
    setLanguages((current) => (current.includes(code) ? current.filter((c) => c !== code) : [...current, code]));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: SignupBody = { portal, name: name.trim(), phone, password };
    if (portal === "ghar") body.locality = locality.trim() || null;
    if (portal === "kaam") {
      body.locality = locality.trim() || null;
      body.trade = trade;
      body.languages = languages;
      if (coords) Object.assign(body, coords);
    }
    if (portal === "sabha") {
      body.role = role;
      body.council_code = councilCode.trim();
    }
    try {
      const { user: created } = await api.auth.signup(body);
      setUser(created);
      navigate(p.home, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = name.trim() && phone.trim() && password.length >= 6 && (portal !== "sabha" || councilCode.trim());

  const nameField = (
    <Field label={portal === "kaam" ? "Your name · आपका नाम" : "Your name"}>
      <label className="field">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" autoComplete="name" aria-label="Full name" required maxLength={100} />
      </label>
    </Field>
  );
  const phoneField = (
    <Field label={portal === "kaam" ? "Mobile number · मोबाइल" : "Mobile number"} hint={`This is your sign-in. One ${p.name} account per number.`}>
      <PhoneField value={phone} onChange={setPhone} />
    </Field>
  );
  const passwordField = (
    <Field label={portal === "kaam" ? "Password · पासवर्ड" : "Password"}>
      <PasswordField value={password} onChange={setPassword} placeholder="At least 6 characters" autoComplete="new-password" minLength={6} />
    </Field>
  );
  const localityField = (
    <Field
      label={portal === "kaam" ? "Where you work from · इलाका" : "Your locality"}
      hint={portal === "kaam" ? "Jobs are matched by distance; tap GPS so the engine knows where you start from." : "Used to find workers close to you. Not shown to anyone."}
    >
      <label className="field">
        <Pin size={20} style={{ color: "var(--accent)" }} />
        <input value={locality} onChange={(e) => setLocality(e.target.value)} placeholder="Area, city" autoComplete="address-level2" aria-label={portal === "kaam" ? "Where you work from" : "Your locality"} maxLength={120} />
        {portal === "kaam" && (
          <button type="button" className="adorn" onClick={useGps} disabled={locating}>
            <Locate size={16} />
            {locating ? "…" : coords ? "Got it" : "GPS"}
          </button>
        )}
      </label>
    </Field>
  );
  const submitButton = (label: string) => (
    <button type="submit" className="btn primary block" disabled={busy || !canSubmit}>
      {busy ? "Creating…" : label}
      {!busy && <ArrowRight size={20} />}
    </button>
  );
  const switchLine = (question: string) => (
    <div className="small" style={{ textAlign: "center", color: "var(--ink-2)" }}>
      {question}{" "}
      <Link to={p.login} style={{ fontWeight: 700 }}>
        Sign in
      </Link>
    </div>
  );

  // ── Sabha: desktop-shaped, the council code comes first ────────────────
  if (portal === "sabha") {
    return (
      <div className="shell" data-portal="sabha">
        <div className="auth-split">
          <aside className="auth-side">
            <Link to={p.landing} className="brand">
              <BrandMark color={p.accent} />
              <Wordmark>
                <small>Cooperative council</small>
              </Wordmark>
              <PortalTag portal="sabha" style={{ marginLeft: 6 }} />
            </Link>
            <div className="stack-lg">
              <h1 style={{ fontSize: 34 }}>The council sees everything. That is why the door is locked.</h1>
              <p style={{ margin: 0, fontSize: 15, lineHeight: 1.55, color: "var(--ink-2)" }}>
                A Sabha account can assign any job, read every worker’s record and the full ledger. Only people the cooperative has given its council code can create one.
              </p>
              <ul className="dot-list">
                <li>Assign work with the engine’s reasons</li>
                <li>Watch every rupee split 85 · 10 · 5</li>
                <li>See next week’s demand by weekday</li>
              </ul>
            </div>
            <div className="small muted">
              Not a council member? Households use <Link to={PORTALS.ghar.landing}>Ghar</Link>, workers use <Link to={PORTALS.kaam.landing}>Kaam</Link>.
            </div>
          </aside>
          <main className="auth-main">
            <form className="stack-lg auth-form" style={{ width: "100%", maxWidth: 460 }} onSubmit={submit}>
              <div className="stack" style={{ gap: 8 }}>
                <div className="label" style={{ color: "var(--accent-d)" }}>Council members only</div>
                <h1 style={{ fontSize: 32 }}>Create a Sabha account</h1>
                {switchLine("Already a member?")}
              </div>
              <Field label="Council code" hint="Ask your cooperative’s secretary for the code. It is checked before anything else.">
                <label className="field">
                  <Lock size={18} style={{ color: "var(--ink-2)" }} />
                  <input
                    value={councilCode}
                    onChange={(e) => setCouncilCode(e.target.value)}
                    placeholder="Council code"
                    autoComplete="off"
                    autoCapitalize="characters"
                    required
                    maxLength={60}
                    style={{ letterSpacing: "0.08em", textTransform: "uppercase" }}
                  />
                </label>
              </Field>
              <div className="grid-2" style={{ gap: 14 }}>
                {nameField}
                <Field label="Role in the cooperative">
                  <label className="field">
                    <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role">
                      {SABHA_ROLES.map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                    </select>
                    <ChevronDown size={18} style={{ color: "var(--ink-3)" }} />
                  </label>
                </Field>
              </div>
              {phoneField}
              {passwordField}
              {error && <div className="notice error">{error}</div>}
              {submitButton("Create council account")}
            </form>
          </main>
        </div>
      </div>
    );
  }

  // ── Ghar and Kaam: phone-shaped ─────────────────────────────────────────
  const heading: ReactNode =
    portal === "kaam" ? (
      <div className="stack" style={{ gap: 6, paddingTop: 12 }}>
        <h1 className="hi" style={{ fontSize: 30, letterSpacing: 0 }}>काम में शामिल हों</h1>
        <div className="sub">Join Kaam. Your cooperative will see your profile and start sharing work with you.</div>
      </div>
    ) : (
      <div className="stack" style={{ gap: 6, paddingTop: 12 }}>
        <h1>Create your Ghar account</h1>
        <div className="sub">Three things and a password. Takes a minute.</div>
      </div>
    );

  return (
    <AuthShell portal={portal}>
      <form className="stack-lg auth-form" onSubmit={submit}>
        {heading}
        {nameField}
        {phoneField}
        {portal === "kaam" && (
          <Field label="What work do you do? · काम" hint="Pick your main trade. The cooperative can change it later.">
            <div className="chips" role="radiogroup" aria-label="Trade">
              {TRADES.map((t) => {
                const IconFor = TRADE_ICONS[t];
                const on = trade === t;
                return (
                  <button type="button" key={t} className={`chip${on ? " on" : ""}`} onClick={() => setTrade(t)} role="radio" aria-checked={on}>
                    {on ? <Check size={14} /> : <IconFor size={14} />}
                    {titleCase(t)}
                  </button>
                );
              })}
            </div>
          </Field>
        )}
        {localityField}
        {portal === "kaam" && (
          <Field label="Languages · भाषा">
            <div className="chips" role="group" aria-label="Languages">
              {LANGUAGES.map((l) => {
                const on = languages.includes(l.code);
                return (
                  <button type="button" key={l.code} className={`chip${on ? " on" : ""}${l.hi ? " hi" : ""}`} onClick={() => toggleLanguage(l.code)} aria-pressed={on}>
                    {l.label}
                  </button>
                );
              })}
            </div>
          </Field>
        )}
        {passwordField}
        {error && <div className="notice error">{error}</div>}
        {submitButton(portal === "kaam" ? "Create my worker account" : "Create account")}
        {portal === "ghar" && (
          <div className="tiny muted" style={{ textAlign: "center", lineHeight: 1.5 }}>
            By creating an account you agree that your bookings and ratings are visible to your cooperative’s council.
          </div>
        )}
        {switchLine(portal === "kaam" ? "Already on Kaam?" : "Already have a Ghar account?")}
      </form>
    </AuthShell>
  );
}
