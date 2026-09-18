/**
 * The Sabha overview, in the order a coordinator needs it: is the
 * cooperative healthy → what needs a hand → what is coming in and who can
 * take it → is work shared fairly → where the fund goes → how we are doing.
 */
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, errorMessage, formatRupees, titleCase, type AttentionItem, type MatchingGroup, type Overview as OverviewT, type TradeRow } from "../../api";
import { AlertCircle, ArrowRight, Check, Sparkle, Star, TrendingUp } from "../../components/Icons";
import { FundPie } from "../../components/sabha/FundPie";
import { SabhaLoop } from "../../components/sabha/SabhaLoop";
import AssistantPanel from "../../components/AssistantPanel";
import { useSabha } from "../../components/SabhaShell";

export default function Overview() {
  const { overview, error, reload } = useSabha();
  if (error && !overview) return <div className="page wide"><div className="notice error">{error}</div></div>;
  if (!overview) return <div className="page wide muted">Loading the cooperative…</div>;
  const o = overview;
  return (
    <div className="page wide sabha-page">
      {error && <div className="notice error">{error}</div>}
      <Metrics o={o} />
      <AssistantPanel role="council" />
      <Attention items={o.attention} />
      <div className="sabha-grid">
        <DemandWorkforce rows={o.trades} />
        <Matching groups={o.matching} onDone={reload} />
      </div>
      <div className="sabha-grid">
        <WorkerNetwork o={o} />
        <FundAllocation o={o} />
      </div>
      <div className="sabha-grid three">
        <Performance o={o} />
        <ResolutionCentre o={o} />
        <ForecastCard o={o} />
      </div>
      <SabhaLoop />
    </div>
  );
}

// ── 1. cooperative health ────────────────────────────────────────────

function Metric({ label, value, suffix, caption, tone }: { label: string; value: string; suffix?: string; caption: string; tone?: "good" | "warn" }) {
  return (
    <div className="metric">
      <div className="label">{label}</div>
      <div className="value num" style={{ color: tone === "good" ? "var(--green-d)" : tone === "warn" ? "var(--terracotta-d)" : undefined }}>
        {value}
        {suffix && <small>{suffix}</small>}
      </div>
      <div className="caption">{caption}</div>
    </div>
  );
}

function lakh(rupees: number): string {
  return rupees >= 100000 ? `₹${(rupees / 100000).toFixed(2)}L` : formatRupees(rupees);
}

function Metrics({ o }: { o: OverviewT }) {
  const { demands, workers, earnings, fairness, fund } = o.metrics;
  const change = earnings.change_pct;
  return (
    <section className="metrics" aria-label="Cooperative health">
      <Metric label="Active demands" value={String(demands.active)} caption={`${demands.unassigned} unassigned · ${demands.ongoing} ongoing · ${demands.completed_today} completed today`} />
      <Metric label="Active workers" value={String(workers.active)} suffix={` / ${workers.registered}`} caption={`${workers.available_now} available today`} />
      <Metric
        label="Worker earnings"
        value={lakh(earnings.this_month_rupees)}
        caption={change === null ? "this month" : `${change >= 0 ? "↑" : "↓"} ${Math.abs(change).toFixed(0)}% vs the same days last month`}
        tone={change !== null && change < 0 ? "warn" : undefined}
      />
      <Metric label="Fairness index" value={String(fairness.index)} suffix=" / 100" caption="Pay · workload · allocation" tone={fairness.index >= 70 ? "good" : fairness.index < 50 ? "warn" : undefined} />
      <Metric label="Cooperative fund" value={formatRupees(fund.total_rupees)} caption={`+${formatRupees(fund.this_month_rupees)} this month`} tone="good" />
    </section>
  );
}

// ── 2. needs attention ───────────────────────────────────────────────

const ATTENTION_LINK: Record<AttentionItem["kind"], string> = {
  assign: "/sabha/demands",
  disputes: "/sabha/disputes",
  workload: "/sabha/workers",
  settle: "/sabha/payments",
  opportunity: "/sabha/demands",
};

function Attention({ items }: { items: AttentionItem[] }) {
  return (
    <section className="panel" id="attention" aria-labelledby="attention-h">
      <div className="row" style={{ gap: 8 }}>
        <AlertCircle size={18} style={{ color: "var(--terracotta)" }} />
        <h2 id="attention-h">Needs attention</h2>
      </div>
      {items.length === 0 ? (
        <div className="small muted">Nothing waiting on the council right now.</div>
      ) : (
        <ul className="attention">
          {items.map((a) => (
            <li key={a.kind} className={`attention-item ${a.level}`}>
              <span className="attention-dot" aria-hidden="true" />
              <span className="grow">{a.text}</span>
              <Link to={a.trade ? `${ATTENTION_LINK[a.kind]}?trade=${a.trade}` : ATTENTION_LINK[a.kind]} className="btn small outline">
                {a.action}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── 3. demand vs workforce ───────────────────────────────────────────

const STATUS_LABEL: Record<TradeRow["status"], { text: string; cls: string }> = {
  good: { text: "Good", cls: "green" },
  moderate: { text: "Moderate", cls: "amber" },
  needs_workers: { text: "Needs workers", cls: "terracotta" },
  idle: { text: "No demand", cls: "grey" },
};

function DemandWorkforce({ rows }: { rows: TradeRow[] }) {
  return (
    <section className="panel" aria-labelledby="dw-h">
      <div className="stack" style={{ gap: 2 }}>
        <h2 id="dw-h">Demand &amp; workforce overview</h2>
        <div className="small muted">Open demand per service against the workers available today</div>
      </div>
      <div className="table">
        <div className="trow head t4">
          <span>Service</span>
          <span>Demand</span>
          <span>Available workers</span>
          <span>Status</span>
        </div>
        {rows.map((r) => (
          <div className="trow t4" key={r.trade}>
            <span style={{ fontWeight: 700 }}>{titleCase(r.trade)}</span>
            <span className="num">
              {r.demand}
              {r.unassigned > 0 && <span className="tiny muted"> · {r.unassigned} open</span>}
            </span>
            <span className="num">{r.available_workers}</span>
            <span>
              <span className={`pill ${STATUS_LABEL[r.status].cls}`}>{STATUS_LABEL[r.status].text}</span>
            </span>
          </div>
        ))}
      </div>
      <Link to="/sabha/demands" className="small" style={{ fontWeight: 700 }}>
        All demands →
      </Link>
    </section>
  );
}

// ── 4. AI matching ───────────────────────────────────────────────────

const AVAIL: Record<string, string> = { available: "Available", unknown: "No schedule declared", unavailable: "Busy" };

function Matching({ groups, onDone }: { groups: MatchingGroup[]; onDone: () => Promise<void> }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  const autoAllocate = async (trade?: string) => {
    setBusy(trade ?? "*");
    setNote(null);
    try {
      const r = await api.allocation.auto(trade);
      setNote({
        kind: "info",
        text: `${r.assigned.length} of ${r.attempted} ${trade ? `${trade} ` : ""}demand${r.attempted === 1 ? "" : "s"} assigned` +
          (r.skipped.length ? `; ${r.skipped.length} skipped (${r.skipped[0].reason})` : "") + ". Every assignment carries its reason.",
      });
      await onDone();
    } catch (e) {
      setNote({ kind: "error", text: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="panel" aria-labelledby="ai-h">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="stack" style={{ gap: 2 }}>
          <div className="row" style={{ gap: 8 }}>
            <Sparkle size={18} style={{ color: "var(--indigo)" }} />
            <h2 id="ai-h">AI matching suggestions</h2>
          </div>
          <div className="small muted">Skill · distance · availability · rating · this week’s workload · fair share</div>
        </div>
        {groups.length > 1 && (
          <button type="button" className="btn small primary" style={{ whiteSpace: "nowrap" }} onClick={() => void autoAllocate()} disabled={busy !== null}>
            <Check size={14} />
            {busy === "*" ? "Allocating…" : `Auto-allocate all (${groups.reduce((n, g) => n + g.unassigned, 0)})`}
          </button>
        )}
      </div>
      {note && <div className={`notice ${note.kind}`}>{note.text}</div>}
      {groups.length === 0 ? (
        <div className="small muted">Every demand has a worker. Nothing to match.</div>
      ) : (
        <div className="stack-lg">
          {groups.slice(0, 3).map((g) => (
            <div className="stack" key={g.trade}>
              <div className="row between" style={{ flexWrap: "wrap", gap: 8 }}>
                <div style={{ fontWeight: 700 }}>
                  {g.unassigned} {g.trade} demand{g.unassigned === 1 ? "" : "s"} require{g.unassigned === 1 ? "s" : ""} workers
                  <span className="tiny muted"> · oldest waiting {g.booking_age_minutes >= 60 ? `${Math.floor(g.booking_age_minutes / 60)} h` : `${g.booking_age_minutes} min`}</span>
                </div>
              </div>
              <ul className="suggestions">
                {g.suggestions.slice(0, 2).map((s) => (
                  <li key={s.worker_id} title={s.explanation}>
                    <span style={{ fontWeight: 700 }}>{s.name}</span>
                    <span className="muted">→ {s.distance_km} km</span>
                    <span className="row" style={{ gap: 3 }}>
                      <Star size={13} filled style={{ color: "var(--terracotta)" }} />
                      {s.rating === null ? "new" : s.rating.toFixed(1)}
                    </span>
                    <span className={`pill ${s.availability === "available" ? "green" : s.availability === "unavailable" ? "terracotta" : "grey"}`}>{AVAIL[s.availability]}</span>
                    <span className="tiny muted">{s.jobs_this_week} this week</span>
                  </li>
                ))}
                {g.suggestions.length === 0 && <li className="small muted">No eligible worker within range — consider opening the trade to nearby members.</li>}
              </ul>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="btn small outline" onClick={() => navigate(`/sabha/demands?trade=${g.trade}`)}>
                  Review matches
                </button>
                <button type="button" className="btn small primary" onClick={() => void autoAllocate(g.trade)} disabled={busy !== null || g.suggestions.length === 0}>
                  <Check size={14} />
                  {busy === g.trade ? "Allocating…" : "Auto-allocate"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ── 5. worker network & workload ─────────────────────────────────────

function WorkerNetwork({ o }: { o: OverviewT }) {
  const n = o.network;
  return (
    <section className="panel" aria-labelledby="wn-h">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="stack" style={{ gap: 2 }}>
          <h2 id="wn-h">Worker network</h2>
          <div className="small muted">Members of the cooperative, and how this week’s work is spread</div>
        </div>
        <Link to="/sabha/workers" className="small" style={{ fontWeight: 700 }}>All workers →</Link>
      </div>
      <div className="grid-2 four">
        <div className="stat"><div className="value">{n.registered}</div><div className="caption">Registered</div></div>
        <div className="stat"><div className="value">{n.active}</div><div className="caption">Active</div></div>
        <div className="stat"><div className="value" style={{ color: "var(--green-d)" }}>{n.available}</div><div className="caption">Available</div></div>
        <div className="stat"><div className="value muted">{n.offline}</div><div className="caption">Offline</div></div>
      </div>
      <div className="stack" style={{ gap: 4 }}>
        <div className="label">Workload distribution · {n.limit} jobs / week limit</div>
        {n.workload.map((w) => (
          <div className="wrow" key={w.worker_id}>
            <span className="ellipsis small" style={{ fontWeight: 600 }}>{w.name}</span>
            <div className="bar">
              <div style={{ width: `${w.pct}%`, background: w.flag === "overloaded" ? "var(--terracotta)" : w.flag === "under_utilised" ? "var(--ramp-3)" : "var(--accent)" }} />
            </div>
            <span className="num small" style={{ fontWeight: 700 }}>{w.pct}%</span>
            <span className="hide-narrow">
              {w.flag === "overloaded" && <span className="pill terracotta">Overloaded</span>}
              {w.flag === "under_utilised" && <span className="pill grey">Under-utilised</span>}
            </span>
          </div>
        ))}
      </div>
      <div className="tiny muted">The engine weighs “fewest jobs this week” at 35% of every pick, so the top of this list drops back down on its own.</div>
    </section>
  );
}

// ── 6. cooperative fund ──────────────────────────────────────────────

function FundAllocation({ o }: { o: OverviewT }) {
  const f = o.metrics.fund;
  return (
    <section className="panel" aria-labelledby="fund-h">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="stack" style={{ gap: 2 }}>
          <h2 id="fund-h">Cooperative fund allocation</h2>
          <div className="small muted">10% of every bill, allocated as the general body decided</div>
        </div>
        <Link to="/sabha/fund" className="small" style={{ fontWeight: 700 }}>Fund →</Link>
      </div>
      <FundPie allocation={f.allocation} total={f.total_rupees} />
    </section>
  );
}

// ── 7. performance, disputes, forecast ───────────────────────────────

function Performance({ o }: { o: OverviewT }) {
  const p = o.performance;
  const rows: [string, string][] = [
    ["Jobs completed", String(p.jobs_completed)],
    ["Workers benefited", String(p.workers_benefited)],
    ["Avg. worker earnings", `${formatRupees(p.avg_worker_earnings_month_rupees)}/month`],
    ["Repeat customers", p.repeat_customers_pct === null ? "—" : `${p.repeat_customers_pct.toFixed(0)}%`],
    ["Disputes resolved", p.disputes_resolved_pct === null ? "—" : `${p.disputes_resolved_pct.toFixed(0)}%`],
    ["Avg. response time", p.avg_response_minutes === null ? "—" : `${Math.round(p.avg_response_minutes)} min`],
  ];
  return (
    <section className="panel" aria-labelledby="perf-h">
      <h2 id="perf-h">Sabha performance</h2>
      <dl className="kv">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd className="num">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ResolutionCentre({ o }: { o: OverviewT }) {
  const d = o.disputes;
  return (
    <section className="panel" aria-labelledby="rc-h">
      <div className="stack" style={{ gap: 2 }}>
        <h2 id="rc-h">Resolution centre</h2>
        <div className="small muted">
          {d.open} Open · {d.resolved} Resolved · {d.resolution_rate === null ? "—" : `${Math.round(d.resolution_rate * 100)}% resolution rate`}
        </div>
      </div>
      {d.recent.length === 0 ? (
        <div className="small muted">No open disputes.</div>
      ) : (
        <div className="stack">
          {d.recent.slice(0, 3).map((x) => (
            <div className="dispute" key={x.id}>
              <div className="stack grow" style={{ gap: 2 }}>
                <div style={{ fontWeight: 700 }}>
                  #{x.id} {x.label}
                </div>
                <div className="tiny muted">
                  {x.raised_by === "customer" ? "Customer → Worker" : x.raised_by === "worker" ? "Worker → Customer" : "Council"}
                  {x.trade ? ` · ${titleCase(x.trade)}` : ""}
                  {x.amount_rupees !== null ? ` · ${formatRupees(x.amount_rupees)}` : ""}
                </div>
              </div>
              <Link to={`/sabha/disputes#d${x.id}`} className="btn small outline">
                {x.kind === "quality" ? "Investigate" : "Review"}
              </Link>
            </div>
          ))}
        </div>
      )}
      <Link to="/sabha/disputes" className="small" style={{ fontWeight: 700 }}>All disputes →</Link>
    </section>
  );
}

function ForecastCard({ o }: { o: OverviewT }) {
  const f = o.forecast_insight;
  return (
    <section className="panel" aria-labelledby="fc-h">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="stack" style={{ gap: 2 }}>
          <h2 id="fc-h">Demand forecast</h2>
          <div className="small muted">Next 7 days{f.trade ? ` · busiest: ${f.trade}` : ""}</div>
        </div>
        <Link to="/sabha/reports" className="small" style={{ fontWeight: 700 }}>Reports →</Link>
      </div>
      <div className="grid-2">
        <div className="stat"><div className="value">{f.expected_bookings.toFixed(0)}</div><div className="caption">expected on peak day{f.peak_weekday ? ` (${f.peak_weekday.slice(0, 3)})` : ""}</div></div>
        <div className="stat"><div className="value">{f.workers_needed}<small> / {f.available_workers}</small></div><div className="caption">workers needed / available</div></div>
      </div>
      <div className="insight">
        <TrendingUp size={18} style={{ color: "var(--indigo-d)", flexShrink: 0 }} />
        <span>{f.text}</span>
      </div>
      <Link to="/sabha/reports" className="row small" style={{ gap: 6, fontWeight: 700 }}>
        See the 7-day chart <ArrowRight size={14} />
      </Link>
    </section>
  );
}
