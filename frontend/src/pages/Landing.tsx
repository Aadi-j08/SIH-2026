import { type CSSProperties, type ReactElement } from "react";
import { Link } from "react-router-dom";

import { type PortalId } from "../api";
import { ArrowDown, ArrowRight, CalendarIcon, Check, Home, ListOrdered, LogIn, Star, Users, Wrench } from "../components/Icons";
import { img, Photo, useImageExists } from "../components/Photo";
import { BrandMark, PORTALS, PORTAL_ORDER, Wordmark } from "../components/PortalShell";
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
const AUDIENCE: Record<PortalId, { label: string; headline: string; points: { title: string }[] }> = {
  ghar: {
    label: "For households",
    headline: "Book in a minute. Know who is coming, and why.",
    points: [
      { title: "Book in a minute" },
      { title: "A fair pick, explained" },
      { title: "Pay after the job" },
      { title: "Rate once, it counts" },
    ],
  },
  kaam: {
    label: "For workers",
    headline: "Say when you’re free. Get your fair share of the work.",
    points: [
      { title: "Availability by voice" },
      { title: "Nobody gets skipped" },
      { title: "85% is yours" },
      { title: "Days that count" },
    ],
  },
  sabha: {
    label: "For the cooperative’s council",
    headline: "Every decision explained. Every rupee visible.",
    points: [
      { title: "Assign with reasons" },
      { title: "An open ledger" },
      { title: "Next week’s demand" },
      { title: "Council members only" },
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
            <Wordmark />
          </div>
          <nav className="nav-links" aria-label="Site">
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
            <div className="stack" style={{ gap: 10 }}>
              <h1>Fair work, close to home.</h1>
              <div className="hi punch">काम भी, इंसाफ़ भी।</div>
            </div>
            <p className="lede" style={{ margin: 0 }}>
              A worker from your neighbourhood’s own cooperative. <strong style={{ color: "var(--ink)" }}>85% of every rupee goes to them.</strong>
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
              <p>Apps pick whoever is closest. New members rarely get a turn.</p>
            </div>
            <div className="problem">
              <h3>Commission first</h3>
              <p>The cut comes out of the worker’s pocket. Nothing comes back.</p>
            </div>
            <div className="problem">
              <h3>Work that counts nowhere</h3>
              <p>Unrecorded days never add up to benefits.</p>
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
          <div className="stack" style={{ gap: 6 }}>
            <h2 className="display" style={{ fontSize: 30 }}>How a job flows</h2>
            <div className="sub">One job, three portals, and the bridge between them.</div>
          </div>
          <ol className="flow" aria-label="How a job flows">
            <FlowStep n={1} portal="ghar" icon={CalendarIcon} title="Household books" text="Trade, place, time. No advance payment." />
            <FlowStep n={2} icon={ListOrdered} title="Engine ranks" text="Four scores, reasons attached." />
            <FlowStep n={3} portal="sabha" icon={Check} title="Council assigns" text="One tap. The reason stays on record." />
            <FlowStep n={4} portal="kaam" icon={Wrench} title="Worker finishes" text="Enters the bill; the ledger splits it." split />
            <FlowStep n={5} portal="ghar" icon={Star} title="Household rates" text="One to five stars." />
          </ol>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <div className="row" style={{ gap: 8 }}>
            <BrandMark size={24} />
            <span className="display" style={{ fontSize: 18, fontWeight: 700, color: "var(--ink)" }}>
              Sahakar<span className="hi">सेतु</span>
            </span>
          </div>
          <span>Household services, run by the neighbourhood’s own cooperative.</span>
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
            <div className="row" style={{ gap: 8, fontWeight: 700 }} key={pt.title}>
              <Check size={18} style={{ color: "var(--accent)" }} />
              {pt.title}
            </div>
          ))}
        </div>
        <div className="row" style={{ gap: 16, flexWrap: "wrap" }}>
          <Link to={p.landing} className="btn primary" style={{ minHeight: 52, fontSize: 16, background: "var(--accent-d)" }}>
            Explore {p.name}
            <ArrowRight size={18} />
          </Link>
        </div>
      </div>
      {!flip && photo}
    </section>
  );
}

/** One node on the flow rail: coloured by the portal that acts (the engine step is ink). */
function FlowStep({ n, portal, icon: IconFor, title, text, split = false }: {
  n: number;
  portal?: PortalId;
  icon: (p: { size?: number }) => ReactElement;
  title: string;
  text: string;
  split?: boolean;
}) {
  return (
    <li className="flow-step" data-portal={portal} data-engine={portal ? undefined : "true"}>
      <div className="flow-node" aria-hidden="true">
        <IconFor size={22} />
        <span className="flow-n">{n}</span>
      </div>
      <div className="flow-body">
        {portal ? (
          <span className={`portal-tag ${portal}`} style={{ height: 24, fontSize: 12, padding: "0 9px" }}>
            {PORTALS[portal].name} · {PORTALS[portal].tag}
          </span>
        ) : (
          <span className="pill grey">Allocation engine</span>
        )}
        <div className="flow-title">{title}</div>
        <p>{text}</p>
        {split && (
          <ul className="split-legend" aria-label="How every bill is split">
            <li><i style={{ background: "var(--green)" }} />85% to the worker</li>
            <li><i style={{ background: "var(--indigo)" }} />10% welfare fund</li>
            <li><i style={{ background: "var(--ink-3)" }} />5% platform</li>
          </ul>
        )}
      </div>
    </li>
  );
}

/** Hero photo; the slot hides itself until the file exists. */
function HeroVisual() {
  return <Photo name="hero.jpg" alt="A plumber from the cooperative fixing a kitchen sink while the household looks on" className="photo hero-photo" />;
}
