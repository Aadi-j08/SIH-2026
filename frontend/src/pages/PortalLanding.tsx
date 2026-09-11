/**
 * A portal's own front page (/ghar, /kaam, /sabha): who it is for, what you
 * get, how it works, and the two ways in. It only ever talks about this
 * portal; the way back to the SahakarSetu home is in the bar and the footer.
 */
import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import { type PortalId } from "../api";
import {
  ArrowLeft, ArrowRight, Bill, CalendarIcon, Check, ListOrdered, Lock, Mic, Receipt, Star, TrendingUp, Users,
} from "../components/Icons";
import { Photo } from "../components/Photo";
import { BrandMark, PORTALS, PortalTag, useThemeColor, Wordmark } from "../components/PortalShell";
import { useAuth } from "../lib/auth";

type IconFn = (p: { size?: number }) => ReactElement;

type Copy = {
  audience: string;
  headline: string;
  lede: string;
  facts: string;
  photo: string;
  create: string;
  signin: string;
  whatTitle: string;
  features: { icon: IconFn; title: string; text: string }[];
  steps: { title: string; text: string }[];
  closing: string;
  notYou: string;
};

const COPY: Record<PortalId, Copy> = {
  ghar: {
    audience: "For households",
    headline: "A plumber, electrician or cleaner from your own cooperative.",
    lede: "Book in a minute. The cooperative’s engine picks who comes — fairly, and with the reason written down. You pay after the job, and see exactly where the money goes.",
    facts: "Free to join · No advance payment · Hindi and English",
    photo: "customer.jpg",
    create: "Create a Ghar account",
    signin: "I already have one — sign in",
    whatTitle: "Everything a booking app does, minus the part that hides how it works.",
    features: [
      { icon: CalendarIcon, title: "Book in a minute", text: "Pick the trade, your locality and a time. That is the whole form." },
      { icon: ListOrdered, title: "See who is coming, and why", text: "Distance, fairness, rating, availability — four scores and one plain sentence." },
      { icon: Bill, title: "Pay after, split openly", text: "The worker enters the bill. 85% to them, 10% to their welfare fund, 5% to the platform." },
      { icon: Star, title: "Rate once, it counts", text: "One to five stars. The worker’s average updates and weighs 20% of the next pick." },
    ],
    steps: [
      { title: "Create your account", text: "Name, mobile number and your locality. That is all we ask." },
      { title: "Book and watch the pick", text: "The cooperative assigns a worker and you see the reasons on your booking." },
      { title: "Pay, then rate", text: "Settle the bill after the job. Your rating shapes the next allocation." },
    ],
    closing: "Create a Ghar account, or sign in if you already have one.",
    notYou: "Not a household?",
  },
  kaam: {
    audience: "For workers",
    headline: "Say when you’re free. Get your fair share of the work.",
    lede: "One sentence in Hindi or English becomes your schedule. Jobs are shared so that nobody gets skipped, 85% of every bill is yours, and every completed job is a recorded day of work.",
    facts: "Free to join · Hindi first · Works on any phone",
    photo: "worker.jpg",
    create: "Join as a worker",
    signin: "Already a member — sign in",
    whatTitle: "Built for the people doing the work, not for the platform.",
    features: [
      { icon: Mic, title: "Availability by voice", text: "“Kal subah free hoon.” One sentence, Hindi or English, becomes your schedule." },
      { icon: Users, title: "Nobody gets skipped", text: "Fewest jobs this week weighs 35% of every pick. Quiet weeks pull you forward." },
      { icon: Receipt, title: "85% is yours", text: "10% goes to your welfare fund, 5% to the platform. Every bill, to the paisa." },
      { icon: Check, title: "Days that count", text: "Every completed job is a recorded day of work toward your benefits." },
    ],
    steps: [
      { title: "Join with your trade", text: "Name, mobile number, what work you do and where you work from." },
      { title: "Say when you’re free", text: "Tap the mic, speak. The cooperative sees your week." },
      { title: "Do the job, enter the bill", text: "The ledger writes 85 / 10 / 5 the moment you finish." },
    ],
    closing: "Join Kaam, or sign in if the cooperative already has you.",
    notYou: "Not a worker?",
  },
  sabha: {
    audience: "For the cooperative’s council",
    headline: "Run the cooperative with every decision explained and every rupee visible.",
    lede: "The engine ranks eligible workers and says why. The council assigns with one tap, watches the ledger split every bill, and sees next week’s demand before it arrives.",
    facts: "Council members only · Needs the council code",
    photo: "cooperative.jpg",
    create: "Create a council account",
    signin: "Sign in",
    whatTitle: "A dashboard the whole cooperative can stand behind.",
    features: [
      { icon: ListOrdered, title: "Assign with reasons", text: "The engine ranks eligible workers; one tap assigns, the reason stays on record." },
      { icon: Receipt, title: "An open ledger", text: "Worker earnings, the welfare fund and the platform’s share, job by job." },
      { icon: TrendingUp, title: "Next week’s demand", text: "Weekday patterns from past bookings say how many workers to keep on call." },
      { icon: Lock, title: "Council members only", text: "A Sabha account needs the cooperative’s council code to be created." },
    ],
    steps: [
      { title: "Get the council code", text: "The cooperative’s secretary shares it with council members offline." },
      { title: "Create your account", text: "The code is checked first; then your name, role and mobile number." },
      { title: "Open the dashboard", text: "Bookings, workers, forecast and ledger — on a laptop or a phone." },
    ],
    closing: "Create a council account with the code, or sign in.",
    notYou: "Not on the council?",
  },
};

export default function PortalLanding({ portal }: { portal: PortalId }) {
  const p = PORTALS[portal];
  const c = COPY[portal];
  const { user } = useAuth();
  const mine = user?.portal === portal;
  useThemeColor(p.accent);

  const enter = (
    <Link to={mine ? p.home : p.signup} className="btn primary">
      {mine ? `Open ${p.name}` : c.create}
      <ArrowRight size={20} />
    </Link>
  );
  const signin = !mine && (
    <Link to={p.login} className="btn outline" style={{ minHeight: 56, fontSize: 15, color: "var(--ink)", borderRadius: "var(--radius-lg)" }}>
      {c.signin}
    </Link>
  );

  return (
    <div className="landing portal-landing" data-portal={portal}>
      <header className="topbar" style={{ borderBottom: "1px solid var(--line)" }}>
        <div className="wrap row between" style={{ gap: 12, flexWrap: "wrap" }}>
          <Link to={p.landing} className="brand">
            <BrandMark color={p.accent} />
            <Wordmark>
              <small>
                {p.name} · {p.tag}
              </small>
            </Wordmark>
            <PortalTag portal={portal} style={{ marginLeft: 6 }} />
          </Link>
          <nav className="nav-links" aria-label="This portal">
            <Link to="/" aria-label="SahakarSetu home">
              <ArrowLeft size={16} />
              <span className="hide-narrow">Home</span>
            </Link>
            <a href="#what" className="hide-narrow">What you get</a>
            <a href="#how" className="hide-narrow">How it works</a>
            {mine ? (
              <Link to={p.home} className="btn small primary" style={{ minHeight: 44, fontSize: 15, borderRadius: 14 }}>
                Open {p.name}
              </Link>
            ) : (
              <>
                <Link to={p.login} className="btn outline" style={{ minHeight: 44, color: "var(--ink)" }}>
                  Sign in
                </Link>
                <Link to={p.signup} className="btn small primary" style={{ minHeight: 44, fontSize: 15, borderRadius: 14 }}>
                  Create account
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <div className="wrap">
        <section className="hero" style={{ paddingBlock: "48px 64px" }}>
          <div className="stack" style={{ gap: 22 }}>
            <div className="label" style={{ letterSpacing: "0.08em", color: "var(--accent-d)" }}>{c.audience}</div>
            <h1 style={{ fontSize: "clamp(36px, 4.5vw, 56px)" }}>{c.headline}</h1>
            <p className="lede" style={{ margin: 0, maxWidth: 540 }}>{c.lede}</p>
            <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
              {enter}
              {signin}
            </div>
            <div className="small muted">{c.facts}</div>
          </div>
          <Photo name={c.photo} alt="" className="photo hero-photo" />
        </section>
      </div>

      <section className="section soft" id="what">
        <div className="wrap">
          <div className="stack" style={{ gap: 10 }}>
            <div className="label" style={{ letterSpacing: "0.08em" }}>What you get</div>
            <h2 className="display">{c.whatTitle}</h2>
          </div>
          <div className="cols-4">
            {c.features.map((f) => {
              const IconFor = f.icon;
              return (
                <div className="feature" key={f.title}>
                  <span className="icon" style={{ background: "var(--accent-t)", color: "var(--accent-d)" }}>
                    <IconFor size={22} />
                  </span>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="section" id="how">
        <div className="wrap">
          <h2 className="display" style={{ fontSize: 30 }}>How it works for you</h2>
          <div className="cols-3">
            {c.steps.map((s, i) => (
              <div className="step" key={s.title}>
                <div className="n" style={{ color: "var(--accent)" }}>{i + 1}</div>
                <div style={{ fontWeight: 700 }}>{s.title}</div>
                <p>{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="wrap" style={{ paddingBottom: 72 }}>
        <div className="closing">
          <div className="stack" style={{ gap: 6 }}>
            <div className="display" style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em" }}>Ready when you are.</div>
            <div style={{ fontSize: 15, color: "var(--ink-on-dark)" }}>{c.closing}</div>
          </div>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <Link to={mine ? p.home : p.signup} className="btn primary" style={{ minHeight: 52, fontSize: 16 }}>
              {mine ? `Open ${p.name}` : "Create account"}
            </Link>
            {!mine && (
              <Link to={p.login} className="btn" style={{ minHeight: 52, border: "1.5px solid #4a403a", color: "var(--paper)" }}>
                Sign in
              </Link>
            )}
          </div>
        </div>
      </div>

      <footer>
        <div className="wrap">
          <div className="row" style={{ gap: 8 }}>
            <span className="display" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
              Sahakar<span className="hi">सेतु</span>
            </span>
            <span>
              · {p.name} · {p.tag}
            </span>
          </div>
          <div className="row" style={{ gap: 18 }}>
            <Link to="/" style={{ color: "inherit" }}>
              {c.notYou} SahakarSetu home
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
