import { useEffect, useState, type CSSProperties, type ReactElement } from "react";
import { Link } from "react-router-dom";

import { api, formatRupees, type Dashboard, type PortalId } from "../api";
import { ArrowDown, ArrowRight, Check, Home, LogIn, Users, Wrench } from "../components/Icons";
import { img, Photo, useImageExists } from "../components/Photo";
import { BrandMark, PORTALS, PORTAL_ORDER } from "../components/PortalShell";
import { useAuth } from "../lib/auth";

/** Section photos, by portal (filenames follow docs/design/image-prompts.md). */
const PORTAL_PHOTO: Record<PortalId, string> = { ghar: "customer.jpg", kaam: "worker.jpg", sabha: "cooperative.jpg" };
const PORTAL_ICON: Record<PortalId, (p: { size?: number }) => ReactElement> = { ghar: Home, kaam: Wrench, sabha: Users };
const PORTAL_FOR: Record<PortalId, string> = {
  ghar: "For households that need a worker.",
  kaam: "For workers who are members of the cooperative.",
  sabha: "For the members who run the cooperative.",
};

/** One section per audience: what that portal gives them, in four points. */
const AUDIENCE: Record<PortalId, { label: string; headline: string; points: { title: string; text: string }[] }> = {
  ghar: {
    label: "For households",
    headline: "Book a worker in a minute, and know why they were chosen.",
    points: [
      { title: "Book in a minute", text: "Trade, place, time. No advance payment." },
      { title: "A fair pick, explained", text: "See the four scores and the reason in plain words before anyone arrives." },
      { title: "Pay after the job", text: "The worker enters the bill; you see it split 85 · 10 · 5 in the open." },
      { title: "Rate once, it counts", text: "One to five stars. The worker’s average updates for the next booking." },
    ],
  },
  kaam: {
    label: "For workers",
    headline: "Say when you’re free. Get your fair share of the work.",
    points: [
      { title: "Availability by voice", text: "“Kal subah free hoon.” One sentence, Hindi or English, becomes your schedule." },
      { title: "Nobody gets skipped", text: "Fewest jobs this week weighs 35% of every pick. Quiet weeks pull you forward." },
      { title: "85% is yours", text: "10% goes to your welfare fund, 5% to the platform. Every bill, to the paisa." },
      { title: "Days that count", text: "Every completed job is a recorded day of work toward your benefits." },
    ],
  },
  sabha: {
    label: "For the cooperative’s council",
    headline: "Run the cooperative with every decision explained and every rupee visible.",
    points: [
      { title: "Assign with reasons", text: "The engine ranks eligible workers; one tap assigns, the reason stays on record." },
      { title: "An open ledger", text: "Worker earnings, the welfare fund and the platform’s share, job by job." },
      { title: "Next week’s demand", text: "Weekday patterns from past bookings say how many workers to keep on call." },
      { title: "Council members only", text: "A Sabha account needs the cooperative’s council code to be created." },
    ],
  },
};

export default function Landing() {
  const { user } = useAuth();
  const bandPhoto = useImageExists("work-itself.jpg");
  const bandStyle: CSSProperties | undefined = bandPhoto
    ? { backgroundImage: `linear-gradient(rgba(38, 29, 23, 0.86), rgba(38, 29, 23, 0.86)), url(${img("work-itself.jpg")})` }
    : undefined;
  return (
    <div className="landing">
      <div className="wrap">
        <header className="topbar">
          <div className="brand">
            <BrandMark />
            <span className="wordmark">SahakarSetu</span>
            <span className="hi hide-narrow" style={{ fontSize: 15, color: "var(--ink-3)" }}>
              सहकार सेतु
            </span>
          </div>
          <nav className="nav-links" aria-label="Portals">
            {PORTAL_ORDER.map((id) => (
              <Link key={id} to={PORTALS[id].landing} className="hide-narrow">
                <span className="dot-mark" style={{ background: PORTALS[id].accent }} />
                {PORTALS[id].name} · {PORTALS[id].tag}
              </Link>
            ))}
            <a href="#how" className="hide-narrow">
              How it works
            </a>
            <Link to={user ? PORTALS[user.portal].home : "/login"} className="btn" style={{ background: "var(--ink)", color: "var(--paper)", borderRadius: 14 }}>
              <LogIn size={18} />
              {user ? `Open ${PORTALS[user.portal].name}` : "Login"}
            </Link>
          </nav>
        </header>

        <section className="hero">
          <div className="stack" style={{ gap: 22 }}>
            <div className="label" style={{ letterSpacing: "0.08em" }}>A bridge to cooperative work</div>
            <h1>Fair work for the neighbourhood, run by the neighbourhood’s own cooperative.</h1>
            <p className="lede" style={{ margin: 0 }}>
              Households book a plumber, electrician or cleaner. The cooperative’s engine picks the worker fairly — and explains why.{" "}
              <strong style={{ color: "var(--ink)" }}>85% of every rupee goes to the worker, 10% to their welfare fund.</strong>
            </p>
            <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
              <Link to={user ? PORTALS[user.portal].home : "/login"} className="btn primary" style={{ background: "var(--ink)", color: "var(--paper)" }}>
                {user ? `Open ${PORTALS[user.portal].name}` : "Sign in or create an account"}
                <ArrowRight size={20} />
              </Link>
              <a href="#how" className="btn outline" style={{ minHeight: 56, fontSize: 15, color: "var(--ink)", borderRadius: "var(--radius-lg)" }}>
                See how it works
                <ArrowDown size={18} />
              </a>
            </div>
            <span className="small muted">Prototype · Smart India Hackathon 2026</span>
          </div>
          <HeroVisual />
        </section>

        <section className="stack" style={{ gap: 18, paddingBottom: 88 }} aria-label="The three portals">
          <div className="row" style={{ alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span className="display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.01em" }}>
              Three portals, one cooperative.
            </span>
            <span className="small muted">Each has its own sign-in. An account opens one portal only.</span>
          </div>
          <div className="doors">
            {PORTAL_ORDER.map((id) => (
              <PortalCard key={id} id={id} />
            ))}
          </div>
        </section>
      </div>

      <section className={`band${bandPhoto ? " has-photo" : ""}`} style={bandStyle}>
        <div className="wrap">
          <div className="stack" style={{ gap: 10 }}>
            <div className="label" style={{ color: "var(--ink-on-dark)", letterSpacing: "0.08em" }}>Why a cooperative</div>
            <h2 className="display">Gig apps are built for the platform. This one is built for the people doing the work.</h2>
          </div>
          <div className="cols-3">
            <div className="problem">
              <h3>Nearest wins, every time</h3>
              <p>Apps route each job to whoever is closest or highest rated. New members and quieter workers rarely get a turn.</p>
            </div>
            <div className="problem">
              <h3>Commission first</h3>
              <p>Platforms take a commission on every job. The cut comes out of the worker’s pocket and nothing comes back to them.</p>
            </div>
            <div className="problem">
              <h3>Work that counts nowhere</h3>
              <p>Benefits for gig workers depend on proving days of engagement. If nobody records them, they never add up.</p>
            </div>
          </div>
        </div>
      </section>

      <div className="wrap stack" style={{ gap: 88, paddingBlock: "88px 88px" }}>
        {PORTAL_ORDER.map((id, i) => (
          <Audience key={id} id={id} flip={i % 2 === 1} />
        ))}
      </div>

      <section className="section soft" id="how">
        <div className="wrap">
          <h2 className="display" style={{ fontSize: 30 }}>How a job flows</h2>
          <div className="steps">
            <Step n={1} color="var(--terracotta)" title="Household books" text="Trade, place, time. No advance payment." />
            <Step n={2} color="var(--terracotta)" title="Engine ranks" text="Eligible workers scored on four factors, reasons attached." />
            <Step n={3} color="var(--indigo)" title="Cooperative assigns" text="One tap in Sabha. The worker’s week count goes up by one." />
            <Step n={4} color="var(--green)" title="Worker finishes" text="Enters the bill in Kaam. Ledger writes 85 / 10 / 5." />
            <Step n={5} color="var(--terracotta)" title="Household rates" text="One to five stars. The worker’s average updates." />
          </div>
        </div>
      </section>

      <LiveNumbers />

      <footer>
        <div className="wrap footer-cols">
          <div className="stack" style={{ gap: 10 }}>
            <div className="row" style={{ gap: 8 }}>
              <BrandMark size={24} />
              <span className="display" style={{ fontSize: 18, fontWeight: 700, color: "var(--ink)" }}>
                SahakarSetu
              </span>
            </div>
            <p className="small" style={{ margin: 0, lineHeight: 1.5, color: "var(--ink-2)", maxWidth: 320 }}>
              A cooperative-run platform for household services. Fair allocation, an open ledger, and a welfare fund for the people doing the work.
            </p>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <div className="label">Portals</div>
            {PORTAL_ORDER.map((id) => (
              <Link key={id} to={PORTALS[id].login} className="row" style={{ gap: 8, color: "var(--ink)", fontWeight: 600, textDecoration: "none" }}>
                <span className="dot-mark" style={{ background: PORTALS[id].accent }} />
                {PORTALS[id].name} · {PORTALS[id].tag}
                <span className="muted" style={{ fontWeight: 500 }}>— sign in</span>
              </Link>
            ))}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <div className="label">Project</div>
            <a href="#how" style={{ color: "var(--ink)", fontWeight: 600, textDecoration: "none" }}>
              How it works
            </a>
            <a href="https://github.com/Aadi-j08/SIH-2026" style={{ color: "var(--ink)", fontWeight: 600, textDecoration: "none" }}>
              GitHub · Aadi-j08/SIH-2026
            </a>
            <a href="/docs" style={{ color: "var(--ink)", fontWeight: 600, textDecoration: "none" }}>
              API docs
            </a>
          </div>
          <div className="footer-line">
            <span>SahakarSetu · Smart India Hackathon 2026</span>
            <span className="hi">सहकार सेतु</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/** Compact card under the hero: names the portal and opens its own landing page. */
function PortalCard({ id }: { id: PortalId }) {
  const p = PORTALS[id];
  const IconFor = PORTAL_ICON[id];
  return (
    <Link to={p.landing} className="portal-card" data-portal={id}>
      <span className="icon" style={{ background: "var(--accent-t)", color: "var(--accent-d)" }}>
        <IconFor size={24} />
      </span>
      <span className="grow stack" style={{ gap: 2 }}>
        <span className="row" style={{ alignItems: "baseline", gap: 6 }}>
          <span className="display" style={{ fontSize: 18, fontWeight: 700 }}>{p.name}</span>
          <span className="hi small muted">{p.hindi}</span>
          <span className="small" style={{ fontWeight: 700, color: "var(--accent-d)" }}>· {p.tag}</span>
        </span>
        <span className="small" style={{ color: "var(--ink-2)", lineHeight: 1.4 }}>{PORTAL_FOR[id]}</span>
      </span>
      <ArrowRight size={20} style={{ color: "var(--accent-d)", flexShrink: 0 }} />
    </Link>
  );
}

/** One audience section: four points and the way into that portal. */
function Audience({ id, flip }: { id: PortalId; flip: boolean }) {
  const p = PORTALS[id];
  const a = AUDIENCE[id];
  const photo = <Photo name={PORTAL_PHOTO[id]} alt="" className="photo audience-photo" />;
  return (
    <section className={`audience${flip ? " flip" : ""}`} data-portal={id} aria-labelledby={`audience-${id}`}>
      {flip && photo}
      <div className="stack" style={{ gap: 22 }}>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <span className={`portal-tag ${id}`}>
            {p.name} · {p.tag}
          </span>
          <span className="label" style={{ letterSpacing: "0.08em" }}>{a.label}</span>
        </div>
        <h2 className="display" id={`audience-${id}`}>{a.headline}</h2>
        <div className="cols-2">
          {a.points.map((pt) => (
            <div className="stack" style={{ gap: 6 }} key={pt.title}>
              <div className="row" style={{ gap: 8, fontWeight: 700 }}>
                <Check size={18} style={{ color: "var(--accent)" }} />
                {pt.title}
              </div>
              <p className="small" style={{ margin: 0, lineHeight: 1.5, color: "var(--ink-2)" }}>{pt.text}</p>
            </div>
          ))}
        </div>
        <div className="row" style={{ gap: 16, flexWrap: "wrap" }}>
          <Link to={p.landing} className="btn primary" style={{ minHeight: 52, fontSize: 16, background: "var(--accent-d)" }}>
            Explore {p.name}
            <ArrowRight size={18} />
          </Link>
          <Link to={p.login} className="small" style={{ fontWeight: 700 }}>
            Sign in to {p.name}
          </Link>
        </div>
      </div>
      {!flip && photo}
    </section>
  );
}

function Step({ n, color, title, text }: { n: number; color: string; title: string; text: string }) {
  return (
    <div className="step">
      <div className="n" style={{ color }}>
        {n}
      </div>
      <div style={{ fontWeight: 700 }}>{title}</div>
      <p>{text}</p>
    </div>
  );
}

function Bar({ label, weight, value }: { label: string; weight: string; value: number }) {
  return (
    <div className="stack" style={{ gap: 4 }}>
      <div className="row between tiny">
        <span className="muted">
          {label} · {weight}
        </span>
        <span style={{ fontWeight: 700 }}>{value}%</span>
      </div>
      <div className="bar thin">
        <div style={{ width: `${value}%`, background: "var(--terracotta)" }} />
      </div>
    </div>
  );
}

/** Hero photo (when present) with the worked allocation example laid over it. */
function HeroVisual() {
  const hasPhoto = useImageExists("hero.jpg");
  return (
    <div className={`hero-visual${hasPhoto ? " has-photo" : ""}`}>
      {hasPhoto && <img className="photo" src={img("hero.jpg")} alt="A plumber from the cooperative fixing a kitchen sink while the household looks on" />}
      <HeroExplanation />
    </div>
  );
}

/** A worked allocation example so the core idea is visible without reading. */
function HeroExplanation() {
  return (
    <aside className="hero-art" aria-label="Example of an explained allocation">
      <div className="label">Why Asha got this job</div>
      <div className="row" style={{ gap: 12 }}>
        <span className="avatar">AV</span>
        <div className="grow stack" style={{ gap: 1 }}>
          <div style={{ fontWeight: 700 }}>Asha Verma</div>
          <div className="small muted">Plumbing · 0.2 km away</div>
        </div>
        <span className="display" style={{ fontSize: 22, fontWeight: 700, color: "var(--green-d)" }}>
          0.99
        </span>
      </div>
      <div className="grid-2" style={{ gap: "8px 14px" }}>
        <Bar label="Proximity" weight="30%" value={100} />
        <Bar label="Fairness" weight="35%" value={100} />
        <Bar label="Rating" weight="20%" value={95} />
        <Bar label="Availability" weight="15%" value={100} />
      </div>
      <p className="small" style={{ margin: 0, lineHeight: 1.45, color: "var(--ink-2)" }}>
        “Asha: 0.2 km from the customer; 1 job this week (fewest in the pool, so fairness favours them); rated 4.8/5; declared available for this slot.”
      </p>
    </aside>
  );
}

function LiveNumbers() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [workerCount, setWorkerCount] = useState<number | null>(null);

  useEffect(() => {
    api.admin.dashboard().then(setDashboard).catch(() => setDashboard(null));
    api.workers.list().then((w) => setWorkerCount(w.length)).catch(() => setWorkerCount(null));
  }, []);

  const value = (n: number | null | undefined, format: (v: number) => string = String) => (n === null || n === undefined ? "—" : format(n));
  return (
    <section className="section">
      <div className="wrap" style={{ gap: 20 }}>
        <div className="row" style={{ alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2 className="display" style={{ fontSize: 30 }}>
            The cooperative today
          </h2>
          <span className="small muted">{dashboard ? "live from the platform" : "connecting…"}</span>
        </div>
        <div className="cols-4 nums">
          <div className="number">
            <div className="value num">{value(workerCount)}</div>
            <div className="small" style={{ color: "var(--ink-2)" }}>
              workers in the cooperative
            </div>
          </div>
          <div className="number">
            <div className="value num">{value(dashboard?.bookings.completed)}</div>
            <div className="small" style={{ color: "var(--ink-2)" }}>
              jobs completed
            </div>
          </div>
          <div className="number">
            <div className="value num" style={{ color: "var(--green-d)" }}>
              {value(dashboard?.money.welfare_fund_rupees, formatRupees)}
            </div>
            <div className="small" style={{ color: "var(--ink-2)" }}>
              in the welfare fund
            </div>
          </div>
          <div className="number">
            <div className="value num">
              {dashboard?.ratings.average == null ? "—" : dashboard.ratings.average.toFixed(1)}
              <span style={{ fontSize: 18, color: "var(--ink-3)" }}> / 5</span>
            </div>
            <div className="small" style={{ color: "var(--ink-2)" }}>
              average rating
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
