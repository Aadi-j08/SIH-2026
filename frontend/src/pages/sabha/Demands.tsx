import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  api,
  errorMessage,
  formatRupees,
  formatWhen,
  titleCase,
  type Booking,
  type BookingDetail,
  type Dashboard,
  type Forecast,
  type Recommendation,
} from "../../api";
import { Check } from "../../components/Icons";
import { useSabha } from "../../components/SabhaShell";

type PendingRow = { booking: Booking; pick: Recommendation | null };

export default function Demands() {
  const { reload: reloadOverview } = useSabha();
  const [params, setParams] = useSearchParams();
  const trade = params.get("trade") ?? "";
  const [pending, setPending] = useState<PendingRow[]>([]);
  const [inProgress, setInProgress] = useState<BookingDetail[]>([]);
  const [trades, setTrades] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [pendingBookings, assignedBookings] = await Promise.all([
        api.bookings.list({ status: "pending" }),
        api.bookings.list({ status: "assigned" }),
      ]);
      setTrades(Array.from(new Set([...pendingBookings, ...assignedBookings].map((b) => b.trade))).sort());
      const rows = await Promise.all(
        pendingBookings.map(async (booking) => ({
          booking,
          pick: (await api.bookings.recommendations(booking.id, 1))[0] ?? null,
        })),
      );
      setPending(rows);
      setInProgress(await Promise.all(assignedBookings.map((b) => api.bookings.detail(b.id))));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const changed = async () => {
    await Promise.all([load(), reloadOverview()]);
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const autoAllocate = async () => {
    setBusy(true);
    setNote(null);
    try {
      const r = await api.allocation.auto(trade || undefined);
      setNote(`${r.assigned.length} of ${r.attempted} assigned${r.skipped.length ? `; ${r.skipped.length} skipped` : ""}.`);
      await changed();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const visible = (t: string) => !trade || t === trade;
  const pendingRows = pending.filter((r) => visible(r.booking.trade));
  const progressRows = inProgress.filter((d) => visible(String(d.booking.trade)));

  return (
    <div className="page wide sabha-page">
      <div className="row between" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div className="stack" style={{ gap: 4 }}>
          <h1 style={{ fontSize: 28 }}>Demands</h1>
          <div className="sub">Every open request, the engine’s pick for it, and the jobs in progress</div>
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <select
            value={trade}
            onChange={(e) => setParams(e.target.value ? { trade: e.target.value } : {})}
            className="chip"
            style={{ minHeight: 36, padding: "0 12px" }}
            aria-label="Filter by trade"
          >
            <option value="">All trades</option>
            {trades.map((t) => (
              <option key={t} value={t}>{titleCase(t)}</option>
            ))}
          </select>
          <button type="button" className="btn small primary" onClick={() => void autoAllocate()} disabled={busy || pendingRows.length === 0}>
            <Check size={14} />
            {busy ? "Allocating…" : `Auto-allocate${trade ? ` ${trade}` : " all"}`}
          </button>
        </div>
      </div>

      {error && <div className="notice error">{error}</div>}
      {note && <div className="notice info">{note}</div>}

      <div className="panel">
        <div className="row" style={{ gap: 8 }}>
          <h2>Unassigned</h2>
          <span className="badge">{pendingRows.length}</span>
          {loading && <span className="tiny muted">refreshing…</span>}
        </div>
        <PendingTable rows={pendingRows} onChanged={changed} />
      </div>

      <div className="panel">
        <div className="row" style={{ gap: 8 }}>
          <h2>In progress</h2>
          <span className="badge">{progressRows.length}</span>
        </div>
        {progressRows.length === 0 ? <div className="small muted">No jobs in progress.</div> : <InProgressList items={progressRows} onChanged={changed} />}
      </div>
    </div>
  );
}

// ── pieces ───────────────────────────────────────────────────────────

export function PendingTable({ rows, onChanged }: { rows: PendingRow[]; onChanged: () => Promise<void> }) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const assign = async (id: number) => {
    setBusyId(id);
    setError(null);
    try {
      await api.bookings.assign(id);
      await onChanged();
    } catch (e) {
      setError(`#${id}: ${errorMessage(e)}`);
    } finally {
      setBusyId(null);
    }
  };

  if (rows.length === 0) return <div className="small muted">Nothing waiting — every booking has a worker.</div>;
  return (
    <div className="table">
      <div className="trow head">
        <div>Booking</div>
        <div className="hide-narrow">Trade</div>
        <div className="hide-narrow">When</div>
        <div className="hide-narrow">Engine's pick</div>
        <div />
      </div>
      {rows.map(({ booking, pick }) => (
        <div className="trow" key={booking.id}>
          <div className="stack" style={{ gap: 2 }}>
            <div style={{ fontWeight: 700 }}>{booking.customer_name}</div>
            <div className="tiny muted num">
              #{booking.id}
              {booking.address ? ` · ${booking.address}` : ""}
            </div>
          </div>
          <div className="small hide-narrow">{titleCase(booking.trade)}</div>
          <div className="small num hide-narrow">{formatWhen(booking.scheduled_for)}</div>
          <div className="stack hide-narrow" style={{ gap: 2, minWidth: 0 }}>
            {pick ? (
              <>
                <div className="small num" style={{ fontWeight: 700 }}>
                  {pick.worker_name} <span style={{ color: "var(--green-d)" }}>{pick.score.toFixed(2)}</span>
                </div>
                <div className="tiny ellipsis" style={{ color: "var(--ink-2)" }} title={pick.explanation}>
                  {pick.explanation.split(": ").slice(1).join(": ")}
                </div>
                {pick.why_selected?.length > 0 && (
                  <div className="tiny muted ellipsis" title={pick.why_selected.join(" · ")}>
                    Why: {pick.why_selected.slice(0, 2).join(" · ")}
                  </div>
                )}
              </>
            ) : (
              <div className="tiny" style={{ color: "var(--terracotta-d)" }}>No eligible worker (trade, distance or availability)</div>
            )}
          </div>
          <button type="button" className="btn small primary" disabled={!pick || busyId === booking.id} onClick={() => assign(booking.id)}>
            {busyId === booking.id ? "…" : "Assign"}
          </button>
        </div>
      ))}
      {error && <div className="notice error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}

export function InProgressList({ items, onChanged }: { items: BookingDetail[]; onChanged: () => Promise<void> }) {
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const complete = async (id: number) => {
    const value = Number(amounts[id]);
    if (!(value > 0)) {
      setError(`#${id}: enter the bill amount in rupees.`);
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      await api.bookings.complete(id, value);
      setAmounts((a) => ({ ...a, [id]: "" }));
      await onChanged();
    } catch (e) {
      setError(`#${id}: ${errorMessage(e)}`);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="stack">
      {items.map(({ booking, assignment }) => (
        <div className="row" key={booking.id} style={{ gap: 12, flexWrap: "wrap" }}>
          <div className="grow stack" style={{ gap: 2, minWidth: 180 }}>
            <div className="small" style={{ fontWeight: 700 }}>
              {booking.customer_name} · {titleCase(booking.trade)}
            </div>
            <div className="tiny muted num">
              #{booking.id} · {formatWhen(booking.scheduled_for)} · {assignment ? String(assignment.worker.name) : "—"}
            </div>
          </div>
          <label className="field" style={{ minHeight: 36, width: 150 }}>
            <span className="muted">₹</span>
            <input inputMode="decimal" value={amounts[booking.id] ?? ""} onChange={(e) => setAmounts((a) => ({ ...a, [booking.id]: e.target.value }))} placeholder="Bill" aria-label="Bill amount" style={{ height: 32 }} />
          </label>
          <button type="button" className="btn small outline" disabled={busyId === booking.id} onClick={() => complete(booking.id)}>
            Mark completed
          </button>
        </div>
      ))}
      {error && <div className="notice error">{error}</div>}
    </div>
  );
}

export function ForecastChart({ forecast }: { forecast: Forecast }) {
  const W = 410;
  const PLOT_TOP = 10;
  const BASE = 150;
  const slot = (W - 24) / 7;
  const maxValue = Math.max(5, ...forecast.points.map((p) => p.upper)) * 1.05;
  const y = (v: number) => BASE - (v / maxValue) * (BASE - PLOT_TOP);
  const gridValues = [0, Math.round(maxValue / 2), Math.round(maxValue)];
  const peak = forecast.points.reduce((best, p) => (p.expected_bookings > best.expected_bookings ? p : best), forecast.points[0]);

  return (
    <div className="stack">
      <svg width="100%" height="200" viewBox={`0 0 ${W} 200`} preserveAspectRatio="xMidYMid meet" fontFamily="Manrope, 'Segoe UI', system-ui, sans-serif" role="img" aria-label={`Forecast: ${forecast.total_expected} bookings expected over ${forecast.horizon_days} days`}>
        <defs>
          <clipPath id="forecast-plot">
            <rect x="0" y="0" width={W} height={BASE} />
          </clipPath>
        </defs>
        <g stroke="var(--line)" strokeWidth="1">
          {gridValues.map((v) => (
            <line key={v} x1="24" y1={y(v)} x2={W} y2={y(v)} />
          ))}
        </g>
        <g fill="var(--ink-3)" fontSize="11" textAnchor="end">
          {gridValues.map((v) => (
            <text key={v} x="18" y={y(v) + 4}>
              {v}
            </text>
          ))}
        </g>
        <g fill="var(--accent-t)">
          {forecast.points.map((p, i) => {
            const cx = 24 + slot * i + slot / 2;
            return <rect key={p.date} x={cx - 10} y={y(p.upper)} width="20" height={Math.max(2, y(p.lower) - y(p.upper))} rx="3" />;
          })}
        </g>
        <g fill="var(--accent)" clipPath="url(#forecast-plot)">
          {forecast.points.map((p, i) => {
            const cx = 24 + slot * i + slot / 2;
            const top = y(p.expected_bookings);
            return <rect key={p.date} x={cx - 6} y={top} width="12" height={Math.max(4, BASE - top + 4)} rx="4" />;
          })}
        </g>
        {peak && peak.expected_bookings > 0 && (
          <text x={24 + slot * forecast.points.indexOf(peak) + slot / 2} y={y(peak.expected_bookings) - 8} fill="var(--ink)" fontSize="11" fontWeight="700" textAnchor="middle">
            {peak.expected_bookings.toFixed(1)}
          </text>
        )}
        <g fill="var(--ink-2)" fontSize="11" textAnchor="middle">
          {forecast.points.map((p, i) => (
            <text key={p.date} x={24 + slot * i + slot / 2} y="168" fontWeight={p === peak ? 700 : 400} fill={p === peak ? "var(--ink)" : undefined}>
              {p.weekday.slice(0, 3)}
            </text>
          ))}
        </g>
        <g>
          {forecast.points.map((p, i) => {
            const cx = 24 + slot * i + slot / 2;
            return (
              <g key={p.date}>
                <rect x={cx - 13} y="178" width="26" height="18" rx="9" fill="var(--paper-2)" />
                <text x={cx} y="191" fill="var(--ink)" fontSize="12" fontWeight="700" textAnchor="middle">
                  {p.workers_needed}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="row tiny muted" style={{ gap: 18, flexWrap: "wrap" }}>
        <span className="row" style={{ gap: 6 }}>
          <span className="swatch" style={{ background: "var(--accent-t)" }} />
          Light band = 80% likely range
        </span>
        <span className="row" style={{ gap: 6 }}>
          <span className="badge" style={{ background: "var(--paper-2)", color: "var(--ink)", height: 16, minWidth: 22, fontSize: 11 }}>
            4
          </span>
          Workers to keep on call that day
        </span>
      </div>
      <div className="tiny muted">
        {forecast.method} · {forecast.history_bookings} booking{forecast.history_bookings === 1 ? "" : "s"} in the last {forecast.history_days} days
      </div>
    </div>
  );
}

export function MoneySplit({ dashboard }: { dashboard: Dashboard }) {
  const { money } = dashboard;
  const rows = [
    { label: "Workers", value: money.worker_payouts_rupees, percent: 85, color: "var(--ramp-1)" },
    { label: "Welfare fund", value: money.welfare_fund_rupees, percent: 10, color: "var(--ramp-2)" },
    { label: "Platform operations", value: money.platform_operations_rupees, percent: 5, color: "var(--ramp-3)" },
  ];
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="split">
        {rows.map((r) => (
          <div key={r.label} style={{ width: `${r.percent}%`, background: r.color }} />
        ))}
      </div>
      <div className="stack" style={{ gap: 8 }}>
        {rows.map((r) => (
          <div className="row" key={r.label}>
            <span className="swatch" style={{ background: r.color }} />
            <span className="grow small" style={{ fontWeight: 600 }}>
              {r.label}
            </span>
            <span className="small num" style={{ fontWeight: 700 }}>
              {formatRupees(r.value)}
            </span>
            <span className="small num muted" style={{ width: 36, textAlign: "right" }}>
              {r.percent}%
            </span>
          </div>
        ))}
      </div>
      {money.gross_rupees === 0 && <div className="tiny muted">No completed jobs yet — the split appears once a booking is marked done.</div>}
    </div>
  );
}
