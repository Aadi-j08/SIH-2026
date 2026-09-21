import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage, formatRupees, type WorkerJob, type WorkerSummary } from "../api";
import { ArrowLeft, Star } from "../components/Icons";
import { RecentJob } from "./Worker";

/** /kaam/jobs — the cooperative story in numbers: the worker's 85%, the 10% and 5%, ratings, every job. */
export default function WorkerJobs() {
  const [summary, setSummary] = useState<WorkerSummary | null>(null);
  const [jobs, setJobs] = useState<WorkerJob[] | null>(null);
  const [range, setRange] = useState<"month" | "all">("month");
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.kaam.summary(), api.kaam.jobs()])
      .then(([s, j]) => {
        setSummary(s);
        setJobs(j);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (error) return <div className="page notice error">{error}</div>;
  if (!summary || !jobs) return <div className="page muted">Loading…</div>;

  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const inRange = (j: WorkerJob) => {
    if (range === "all") return true;
    const when = j.completed_at ?? j.declined_at ?? j.assigned_at;
    return when ? new Date(when.includes("T") ? when : when.replace(" ", "T") + "Z") >= monthStart : true;
  };
  const finished = jobs.filter((j) => (j.outcome === "completed" || j.outcome === "declined") && inRange(j));
  const completed = finished.filter((j) => j.outcome === "completed");
  const share = range === "month" ? summary.share_this_month_rupees : summary.share_rupees;
  const billed = range === "month" ? summary.billed_this_month_rupees : completed.reduce((s, j) => s + (j.billed_rupees ?? 0), 0);
  const split = summary.split_percent;
  const welfare = Math.round((billed * split.welfare_fund) / 100);
  const ops = Math.round((billed * split.platform_operations) / 100);
  const monthName = new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  const visible = showAll ? finished : finished.slice(0, 4);

  return (
    <div className="page">
      <div className="row" style={{ gap: 12 }}>
        <Link to="/kaam/home" className="btn outline" style={{ width: 44, minHeight: 44, padding: 0 }} aria-label="Back to home">
          <ArrowLeft size={20} />
        </Link>
        <div className="stack grow" style={{ gap: 1 }}>
          <div className="display" style={{ fontSize: 20, fontWeight: 700 }}>Jobs &amp; earnings</div>
          <div className="small muted">
            {range === "month" ? monthName : "All time"} · <span className="hi">काम और कमाई</span>
          </div>
        </div>
        <div className="seg">
          {(["month", "all"] as const).map((r) => (
            <a key={r} href="#" className={range === r ? "active" : ""} onClick={(e) => { e.preventDefault(); setRange(r); }} style={range === r ? { background: "var(--ink)", color: "var(--paper)" } : undefined}>
              {r === "month" ? "Month" : "All"}
            </a>
          ))}
        </div>
      </div>

      <div className="card dark stack" style={{ gap: 12, padding: 16, borderRadius: "var(--radius-xl)" }}>
        <div className="row between" style={{ alignItems: "flex-end" }}>
          <div className="stack" style={{ gap: 2 }}>
            <div className="label" style={{ color: "var(--ink-on-dark)" }}>Your share {range === "month" ? "this month" : "all time"}</div>
            <div className="display num" style={{ fontSize: 34, fontWeight: 700, lineHeight: 1 }}>{formatRupees(share)}</div>
          </div>
          <div className="stack tiny" style={{ alignItems: "flex-end", gap: 2, color: "var(--ink-on-dark)" }}>
            <span>from {completed.length} job{completed.length === 1 ? "" : "s"}</span>
            <span>{formatRupees(billed)} billed</span>
          </div>
        </div>
        <div className="split-bar">
          <div style={{ width: `${split.worker}%`, background: "var(--green)" }} />
          <div style={{ width: `${split.welfare_fund}%`, background: "var(--ink-on-dark)" }} />
          <div style={{ width: `${split.platform_operations}%`, background: "#7a6f66" }} />
        </div>
        <div className="grid-3" style={{ gap: 8 }}>
          {[
            ["You", split.worker, share, "var(--green)"],
            ["Welfare fund", split.welfare_fund, welfare, "var(--ink-on-dark)"],
            ["Running costs", split.platform_operations, ops, "#7a6f66"],
          ].map(([name, pct, value, color]) => (
            <div key={String(name)} className="stack" style={{ gap: 1 }}>
              <div className="row tiny" style={{ gap: 5, color: "var(--ink-on-dark)", whiteSpace: "nowrap" }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: String(color), display: "inline-block", flexShrink: 0 }} />
                {name}
              </div>
              <div className="display num" style={{ fontSize: 15, fontWeight: 700 }}>
                {formatRupees(Number(value))} <small style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-on-dark)" }}>{pct}%</small>
              </div>
            </div>
          ))}
        </div>
        <div id="benefits" className="tiny" style={{ lineHeight: 1.4, color: "var(--ink-on-dark)" }}>
          The welfare fund pays for member benefits after {summary.eligibility_days} active days —{" "}
          <b style={{ color: "var(--paper)" }}>{summary.engagement_days} down, {summary.days_to_benefits} to go</b>. An active day is any day you finished a job.
        </div>
      </div>

      <div className="card soft row" style={{ gap: 12 }}>
        <div className="display num" style={{ fontSize: 24, fontWeight: 700 }}>{summary.rating !== null ? summary.rating.toFixed(1) : "—"}</div>
        <div className="stack grow" style={{ gap: 1 }}>
          <div className="row" style={{ gap: 2, fontWeight: 700 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <Star key={n} size={14} filled={summary.rating !== null && n <= Math.round(summary.rating)} />
            ))}
            <span style={{ marginLeft: 6 }}>from {summary.rating_count} rating{summary.rating_count === 1 ? "" : "s"}</span>
          </div>
          <div className="tiny muted">Ratings are 20% of how the engine picks you. Fairness (fewest jobs) is 35%.</div>
        </div>
      </div>

      <section className="stack">
        <div className="label">{range === "month" ? "This month" : "Every job"}</div>
        {finished.length === 0 ? (
          <div className="card soft small muted">Nothing finished {range === "month" ? "this month" : "yet"}.</div>
        ) : (
          <div className="stack" style={{ gap: 6 }}>
            {visible.map((j) => (
              <RecentJob key={`${j.outcome}-${j.booking_id}`} job={j} />
            ))}
          </div>
        )}
        {finished.length > 4 && !showAll && (
          <button type="button" className="btn soft" onClick={() => setShowAll(true)}>
            Show {finished.length - 4} more
          </button>
        )}
      </section>
    </div>
  );
}
