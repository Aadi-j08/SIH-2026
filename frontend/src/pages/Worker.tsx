import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage, formatRupees, titleCase, type Worker as WorkerT, type WorkerJob, type WorkerSummary } from "../api";
import JobCard from "../components/JobCard";
import { Check, Clock, Mic, Star } from "../components/Icons";
import VoiceAvailability from "../components/VoiceAvailability";
import { useAuth } from "../lib/auth";
import { buildWeek, SLOTS, type WeekDay } from "../lib/week";

/** Kaam home: the job that needs a reply, the week at a glance, the mic, real numbers, recent jobs. */
export default function Worker() {
  const { user } = useAuth();
  const [worker, setWorker] = useState<WorkerT | null>(null);
  const [summary, setSummary] = useState<WorkerSummary | null>(null);
  const [jobs, setJobs] = useState<WorkerJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const workerId = user?.worker_id ?? null;

  const refresh = useCallback(async () => {
    if (workerId === null) return;
    try {
      const [w, s, j] = await Promise.all([api.workers.get(workerId), api.kaam.summary(), api.kaam.jobs()]);
      setWorker(w);
      setSummary(s);
      setJobs(j);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [workerId]);

  useEffect(() => {
    if (workerId === null) {
      setError("This Kaam account is not linked to a worker record. Ask the cooperative to fix it.");
      return;
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(timer);
  }, [workerId, refresh]);

  if (error && !worker) return <div className="page notice error">{error}</div>;
  if (!worker || !summary || !jobs) return <div className="page muted">Loading…</div>;

  if (worker.status === "pending") {
    return (
      <div className="page">
        <Greeting worker={worker} summary={summary} pending />
        <PendingApproval user={user?.locality ?? null} phone={user?.phone ?? null} />
        <VoiceAvailability worker={worker} onSaved={(w) => { setWorker(w); void refresh(); }} compact />
        <WeekStrip worker={worker} jobs={jobs} summary={summary} />
      </div>
    );
  }

  const open = jobs.filter((j) => j.outcome === "assigned" || j.outcome === "accepted");
  const recent = jobs.filter((j) => j.outcome === "completed" || j.outcome === "declined").slice(0, 2);

  return (
    <div className="page">
      {error && <div className="notice error">{error}</div>}
      <Greeting worker={worker} summary={summary} />
      {open.length > 0 && (
        <section className="stack">
          {open.map((job) => (
            <JobCard key={job.booking_id} job={job} onChange={refresh} />
          ))}
        </section>
      )}
      <WeekStrip worker={worker} jobs={jobs} summary={summary} />
      <VoiceAvailability worker={worker} onSaved={(w) => { setWorker(w); void refresh(); }} compact />
      <Stats summary={summary} />
      <section className="stack">
        <div className="row between">
          <div className="label">Recent jobs</div>
          <Link to="/kaam/jobs" className="link">All jobs &amp; earnings →</Link>
        </div>
        {recent.length === 0 ? (
          <div className="card soft small muted">No finished jobs yet. Keep your week green and the engine will send work your way.</div>
        ) : (
          recent.map((j) => <RecentJob key={j.booking_id} job={j} />)
        )}
      </section>
      <div className="card soft row" style={{ gap: 12 }}>
        <span className="avatar small-avatar">{worker.name.slice(0, 1)}</span>
        <div className="stack grow" style={{ gap: 1 }}>
          <div style={{ fontWeight: 700 }}>My profile</div>
          <div className="tiny muted">
            {titleCase(worker.trade)}{user?.locality ? ` · ${user.locality}` : ""}{user?.languages?.length ? ` · ${user.languages.join(", ")}` : ""}{worker.phone ? ` · ${worker.phone}` : ""}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── pieces ───────────────────────────────────────────────────────────

function Greeting({ worker, summary, pending = false }: { worker: WorkerT; summary: WorkerSummary; pending?: boolean }) {
  const initials = worker.name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className="row between">
      <div className="stack" style={{ gap: 3 }}>
        <div className="row" style={{ alignItems: "baseline", gap: 8 }}>
          <span className="hi" style={{ fontSize: 22, fontWeight: 600 }}>नमस्ते,</span>
          <span className="display" style={{ fontSize: 24, fontWeight: 700 }}>{worker.name.split(" ")[0]}</span>
        </div>
        <div className="row small muted" style={{ gap: 8 }}>
          <span>{titleCase(worker.trade)}</span>
          {pending ? (
            <span className="pill amber">Awaiting council approval</span>
          ) : (
            <>
              <span>· Cooperative member</span>
              {summary.rating !== null && (
                <span className="row" style={{ gap: 3 }}>
                  · <Star size={13} filled /> {summary.rating.toFixed(1)}
                </span>
              )}
            </>
          )}
        </div>
      </div>
      <span className="avatar" style={pending ? { background: "var(--paper-2)", color: "var(--ink-2)" } : undefined}>{initials}</span>
    </div>
  );
}

function PendingApproval({ user, phone }: { user: string | null; phone: string | null }) {
  return (
    <section className="stack">
      <div className="card stack" style={{ gap: 12, padding: 16, borderRadius: "var(--radius-xl)" }}>
        <div className="stack" style={{ gap: 3 }}>
          <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>Your profile is with the council</div>
          <div className="hi small muted">सभा आपकी प्रोफ़ाइल देख रही है — आमतौर पर 1 दिन में</div>
        </div>
        <div className="timeline">
          <div className="tl-step">
            <div className="tl-rail"><span className="node done"><Check size={13} strokeWidth={3} /></span><span className="line done" /></div>
            <div className="tl-text"><b style={{ fontSize: 14 }}>Account created</b><span className="tiny muted">Just now</span></div>
          </div>
          <div className="tl-step">
            <div className="tl-rail"><span className="node now"><Clock size={13} strokeWidth={2.5} /></span><span className="line" /></div>
            <div className="tl-text"><b style={{ fontSize: 14 }}>Council checks your trade and area</b><span className="tiny muted">A member may call you{phone ? ` on ${phone}` : ""}</span></div>
          </div>
          <div className="tl-step">
            <div className="tl-rail"><span className="node next" /></div>
            <div className="tl-text"><b style={{ fontSize: 14, color: "var(--ink-3)" }}>You start getting jobs</b><span className="tiny muted">The engine matches you by distance, fairness, rating and your free hours</span></div>
          </div>
        </div>
      </div>
      <div className="label">Meanwhile — get ready</div>
      <div className="card row" style={{ gap: 12 }}>
        <span className="dot green"><Mic size={15} /></span>
        <div className="stack grow" style={{ gap: 1 }}>
          <div style={{ fontWeight: 700 }}>1 · Tell us when you’re free</div>
          <div className="tiny muted">Use the mic below — “somvar se shukravar subah khali hoon”</div>
        </div>
      </div>
      <div className="card row" style={{ gap: 12 }}>
        <span className="dot grey display" style={{ fontWeight: 700, fontSize: 13 }}>2</span>
        <div className="stack grow" style={{ gap: 1 }}>
          <div style={{ fontWeight: 700 }}>Check your area is right</div>
          <div className="tiny muted">{user ?? "No area saved"} · jobs are matched by distance</div>
        </div>
      </div>
      <div className="card row" style={{ gap: 12 }}>
        <span className="dot grey display" style={{ fontWeight: 700, fontSize: 13 }}>3</span>
        <div className="stack grow" style={{ gap: 1 }}>
          <div style={{ fontWeight: 700 }}>How the cooperative pays</div>
          <div className="tiny muted">85% of every job to you · welfare fund 10% · running costs 5% · benefits after 90 active days</div>
        </div>
      </div>
    </section>
  );
}

export function WeekStrip({ worker, jobs, summary }: { worker: WorkerT; jobs: WorkerJob[]; summary: WorkerSummary }) {
  const week: WeekDay[] = buildWeek(worker.availability, jobs);
  return (
    <section className="stack" style={{ gap: 8 }}>
      <div className="row between">
        <div className="label">My week · <span className="hi" style={{ textTransform: "none", letterSpacing: 0 }}>मेरा हफ़्ता</span></div>
        <Link to="/kaam/week" className="link">Open week →</Link>
      </div>
      <div className="week-strip">
        {week.map((day) => (
          <Link key={day.date} to={`/kaam/week?day=${day.date}`} className={day.isToday ? "today" : ""} aria-label={`${day.label} ${day.dayNumber}`}>
            <span className="dow">{day.label}</span>
            <span className="dnum">{day.dayNumber}</span>
            <span className="slot-bars">
              {day.slots.map((s) => (
                <span key={s.slot} className={s.state} />
              ))}
            </span>
          </Link>
        ))}
      </div>
      <div className="legend">
        <span><i className="legend-swatch free" />Free</span>
        <span><i className="legend-swatch" />Not set</span>
        <span><i className="legend-swatch busy" />Busy / job</span>
        <span className="muted" style={{ marginLeft: "auto" }}>{SLOTS.map((s) => s.label.toLowerCase()).join(" · ")}</span>
      </div>
      {summary.free_hours_this_week === 0 && worker.status === "active" && (
        <div className="notice warn">You have no free hours this week, so the engine can’t offer you anything. Tap a day above or use the mic.</div>
      )}
    </section>
  );
}

function Stats({ summary }: { summary: WorkerSummary }) {
  const days = summary.engagement_days;
  return (
    <section className="grid-3" style={{ gap: 8 }}>
      <div className="stat">
        <div className="value num">{summary.jobs_this_week}</div>
        <div className="caption">jobs this week</div>
      </div>
      <div className="stat">
        <div className="value num">{formatRupees(summary.share_this_month_rupees)}</div>
        <div className="caption">your share this month</div>
      </div>
      <div className="stat" style={{ gap: 6 }}>
        <div className="value num">
          {days}
          <small> / {summary.eligibility_days}</small>
        </div>
        <div className="stack" style={{ gap: 4 }}>
          <div className="bar thin">
            <div style={{ width: `${Math.min(100, Math.round((days / summary.eligibility_days) * 100))}%` }} />
          </div>
          <div className="caption" style={{ fontSize: 11, lineHeight: 1.2 }}>
            days to benefits · <Link to="/kaam/jobs#benefits" className="link" style={{ fontSize: 11 }}>what’s that?</Link>
          </div>
        </div>
      </div>
    </section>
  );
}

export function RecentJob({ job }: { job: WorkerJob }) {
  const when = job.completed_at ?? job.declined_at ?? job.scheduled_for;
  const date = when ? new Date(when.includes("T") ? when : when.replace(" ", "T") + "Z").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }) : "";
  return (
    <div className="card row" style={{ gap: 12, padding: "10px 12px 10px 14px", background: job.outcome === "declined" ? "var(--paper-2)" : undefined, borderColor: job.outcome === "declined" ? "var(--paper-2)" : undefined }}>
      <div className="stack grow" style={{ gap: 2 }}>
        <div style={{ fontWeight: 700, color: job.outcome === "declined" ? "var(--ink-2)" : undefined }}>
          {job.customer_name} · {titleCase(job.trade)}
        </div>
        <div className="tiny muted">
          {date}
          {job.outcome === "completed" && (job.rating ? ` · ${"★".repeat(job.rating)}${"☆".repeat(5 - job.rating)}` : " · not rated yet")}
          {job.outcome === "declined" && ` · passed on (${(job.decline_reason ?? "other").replace(/_/g, " ")}) · no penalty`}
        </div>
      </div>
      {job.outcome === "completed" && job.share_rupees !== null ? (
        <div className="stack" style={{ alignItems: "flex-end", gap: 1 }}>
          <div className="display num" style={{ fontSize: 15, fontWeight: 700, color: "var(--green-d)" }}>{formatRupees(job.share_rupees)}</div>
          {job.billed_rupees !== null && <div className="muted" style={{ fontSize: 11 }}>of {formatRupees(job.billed_rupees)}</div>}
        </div>
      ) : (
        <div className="small muted" style={{ fontWeight: 700 }}>—</div>
      )}
    </div>
  );
}
