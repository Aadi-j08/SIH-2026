import { useEffect, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";

import { api, formatRupees, type Dashboard } from "../api";
import { ArrowDown, ArrowRight, ListOrdered, Mic, Receipt, TrendingUp } from "../components/Icons";
import { BrandMark, PORTALS, type PortalId } from "../components/PortalShell";

const ORDER: PortalId[] = ["ghar", "kaam", "sabha"];

/** Photos live in frontend/public/img (see the README there). A slot hides itself until its file exists. */
const img = (name: string) => `${import.meta.env.BASE_URL}img/${name}`;

/** Door photos, by portal (filenames follow docs/design/image-prompts.md). */
const DOOR_PHOTO: Record<PortalId, string> = { ghar: "customer.jpg", kaam: "worker.jpg", sabha: "cooperative.jpg" };

function Photo({ name, alt, className = "photo" }: { name: string; alt: string; className?: string }) {
  const [missing, setMissing] = useState(false);
  if (missing) return null;
  return <img className={className} src={img(name)} alt={alt} loading="lazy" onError={() => setMissing(true)} />;
}

/** True once the browser has confirmed the file exists; used for background photos. */
function useImageExists(name: string): boolean {
  const [exists, setExists] = useState(false);
  useEffect(() => {
    const probe = new Image();
    probe.onload = () => setExists(true);
    probe.src = img(name);
  }, [name]);
  return exists;
}

export default function Landing() {
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
            <span className="hi" style={{ fontSize: 15, color: "var(--ink-3)" }}>
              सहकार सेतु
            </span>
          </div>
          <nav className="tags" aria-label="Portals">
            {ORDER.map((id) => (
              <Link key={id} to={PORTALS[id].path} className={`portal-tag ${id}`}>
                {PORTALS[id].name} · {PORTALS[id].tag}
              </Link>
            ))}
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
              <a href="#how" className="btn primary" style={{ background: "var(--ink)", color: "var(--paper)", textDecoration: "none" }}>
                See how it works
                <ArrowDown size={20} />
              </a>
              <span className="small muted">Prototype · Smart India Hackathon 2026</span>
            </div>
          </div>
          <HeroVisual />
        </section>

        <section className="doors" aria-label="Choose a portal">
          {ORDER.map((id) => (
            <Door key={id} id={id} />
          ))}
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

      <section className="section">
        <div className="wrap">
          <div className="stack" style={{ gap: 10 }}>
            <div className="label" style={{ letterSpacing: "0.08em" }}>What SahakarSetu does differently</div>
            <h2 className="display">Four things, each one visible to everyone.</h2>
          </div>
          <div className="cols-4">
            <div className="feature">
              <Photo name="neighbourhood.jpg" alt="" />
              <span className="icon" style={{ background: "var(--terracotta-t)", color: "var(--terracotta-d)" }}>
                <ListOrdered size={22} />
              </span>
              <h3>Fair allocation, explained</h3>
              <p>Every job is scored on distance (30%), who has had the fewest jobs this week (35%), rating (20%) and declared availability (15%). The pick arrives with its reason in plain words.</p>
            </div>
            <div className="feature">
              <Photo name="worker.jpg" alt="" />
              <span className="icon" style={{ background: "var(--green-t)", color: "var(--green-d)" }}>
                <Mic size={22} />
              </span>
              <h3>Availability by voice</h3>
              <p>“Kal subah free hoon lekin shaam ko nahi.” One sentence, Hindi or English, becomes a schedule. No forms, no typing.</p>
            </div>
            <div className="feature">
              <Photo name="money.jpg" alt="" />
              <span className="icon" style={{ background: "var(--paper-2)", color: "var(--ink-2)" }}>
                <Receipt size={22} />
              </span>
              <h3>85 · 10 · 5</h3>
              <p>Worker · welfare fund · platform. Every bill is split to the paisa and the ledger is open to the customer, the worker and the cooperative.</p>
            </div>
            <div className="feature">
              <Photo name="demand-forecast.jpg" alt="" />
              <span className="icon" style={{ background: "var(--indigo-t)", color: "var(--indigo-d)" }}>
                <TrendingUp size={22} />
              </span>
              <h3>Demand forecast</h3>
              <p>Weekday patterns from past bookings tell the cooperative how many workers to keep on call each day of the coming week.</p>
            </div>
          </div>
        </div>
      </section>

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
        <div className="wrap">
          <div className="row" style={{ gap: 8 }}>
            <span className="display" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
              SahakarSetu
            </span>
            <span>· Smart India Hackathon 2026</span>
          </div>
          <div className="row" style={{ gap: 18 }}>
            <a href="https://github.com/Aadi-j08/SIH-2026" style={{ color: "inherit" }}>
              GitHub
            </a>
            <a href="/docs" style={{ color: "inherit" }}>
              API docs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Door({ id }: { id: PortalId }) {
  const p = PORTALS[id];
  return (
    <Link to={p.path} className="door" data-portal={id}>
      <Photo name={DOOR_PHOTO[id]} alt="" />
      <div className="row between">
        <span className="name">
          {p.name} <span className="hi">{p.hindi}</span>
        </span>
        <span className={`portal-tag ${id}`} style={{ height: 28 }}>
          {p.tag}
        </span>
      </div>
      <div style={{ fontSize: 16, fontWeight: 700 }}>{p.who}</div>
      <p className="small" style={{ margin: 0, lineHeight: 1.5, color: "var(--ink-2)" }}>
        {p.blurb}
      </p>
      <span className="btn primary" style={{ minHeight: 48, fontSize: 15, background: "var(--accent-d)" }}>
        {p.cta}
        <ArrowRight size={18} />
      </span>
    </Link>
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
