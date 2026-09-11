/**
 * The common gateway at /login: pick who you are, then go to that portal's
 * own sign-in. Accounts never cross portals, and this page says so.
 */
import { Link } from "react-router-dom";

import { type PortalId } from "../api";
import { ArrowLeft, ArrowRight, Lock, Shield } from "../components/Icons";
import { BrandMark, PORTALS, PORTAL_ORDER } from "../components/PortalShell";
import { Photo } from "../components/Photo";
import { useAuth } from "../lib/auth";

const PHOTO: Record<PortalId, string> = { ghar: "customer.jpg", kaam: "worker.jpg", sabha: "cooperative.jpg" };
const BLURB: Record<PortalId, string> = {
  ghar: "For households booking a plumber, electrician or cleaner.",
  kaam: "For members of the cooperative who do the work.",
  sabha: "For council members. Creating an account needs the council code.",
};
const NEW_HERE: Record<PortalId, string> = { ghar: "New here? Create a Ghar account", kaam: "New here? Join as a worker", sabha: "I have a council code" };

export default function Login() {
  const { user } = useAuth();
  return (
    <div className="landing">
      <div className="wrap">
        <header className="topbar">
          <Link to="/" className="brand">
            <BrandMark />
            <span className="wordmark">SahakarSetu</span>
            <span className="hi hide-narrow" style={{ fontSize: 15, color: "var(--ink-3)" }}>
              सहकार सेतु
            </span>
          </Link>
          <Link to="/" className="back">
            <ArrowLeft size={16} />
            Back to home
          </Link>
        </header>

        <section className="stack" style={{ alignItems: "center", textAlign: "center", gap: 12, paddingBlock: "32px 36px" }}>
          <div className="label" style={{ letterSpacing: "0.08em" }}>Sign in · Create account</div>
          <h1 className="display" style={{ fontSize: "clamp(32px, 4vw, 44px)", letterSpacing: "-0.03em" }}>
            Who are you signing in as?
          </h1>
          <div className="hi" style={{ fontSize: 20, color: "var(--ink-2)" }}>
            आप किस रूप में आए हैं?
          </div>
        </section>

        <section className="choices" aria-label="Portals">
          {PORTAL_ORDER.map((id) => {
            const p = PORTALS[id];
            const mine = user?.portal === id;
            return (
              <div key={id} className="choice" data-portal={id}>
                <Photo name={PHOTO[id]} alt="" className="photo choice-photo" />
                <div className="row between">
                  <span className="name">
                    {p.name} <span className="hi">{p.hindi}</span>
                  </span>
                  <span className={`portal-tag ${id}`} style={{ height: 28 }}>
                    {p.tag}
                  </span>
                </div>
                <div className="stack" style={{ gap: 4 }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{p.who}</div>
                  <p className="small" style={{ margin: 0, lineHeight: 1.5, color: "var(--ink-2)" }}>
                    {BLURB[id]}
                  </p>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  <Link to={mine ? p.home : p.login} className="btn primary" style={{ minHeight: 50, fontSize: 15, background: "var(--accent-d)" }}>
                    {mine ? `Open ${p.name}` : `Sign in to ${p.name}`}
                    <ArrowRight size={18} />
                  </Link>
                  {!mine && (
                    <Link to={p.signup} className="btn outline" style={{ color: "var(--ink)" }}>
                      {id === "sabha" && <Lock size={14} />}
                      {NEW_HERE[id]}
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </section>

        <div className="row" style={{ justifyContent: "center", paddingBlock: "32px 64px" }}>
          <div className="notice info row" style={{ gap: 10, alignItems: "flex-start", maxWidth: 640 }}>
            <Shield size={18} style={{ flexShrink: 0, color: "var(--ink-3)", marginTop: 1 }} />
            <span>
              Each portal keeps its own accounts. A Ghar sign-in cannot open Kaam or Sabha, and the other way round. The same phone number can hold one account in each.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
