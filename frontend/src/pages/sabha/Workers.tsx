/** Worker network: every member, their trade, rating, this week's load, and whether the engine can reach them today. */
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, errorMessage, titleCase, type Worker } from "../../api";
import { Star } from "../../components/Icons";
import PendingWorkers from "../../components/PendingWorkers";
import { useSabha } from "../../components/SabhaShell";

export default function Workers() {
  const { overview } = useSabha();
  const [params, setParams] = useSearchParams();
  const trade = params.get("trade") ?? "";
  const [workers, setWorkers] = useState<Worker[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.workers.list().then(setWorkers).catch((e) => setError(errorMessage(e)));
  }, []);

  const limit = overview?.network.limit ?? 6;
  const trades = useMemo(() => Array.from(new Set((workers ?? []).map((w) => w.trade))).sort(), [workers]);
  const rows = (workers ?? []).filter((w) => !trade || w.trade === trade).sort((a, b) => b.jobs_this_week - a.jobs_this_week || a.name.localeCompare(b.name));
  const n = overview?.network;

  return (
    <div className="page wide sabha-page">
      <div className="row between" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div className="stack" style={{ gap: 4 }}>
          <h1 style={{ fontSize: 28 }}>Worker network</h1>
          <div className="sub">Members of the cooperative who do the work. Sabha coordinates; it does not employ.</div>
        </div>
        <select value={trade} onChange={(e) => setParams(e.target.value ? { trade: e.target.value } : {})} className="chip" style={{ minHeight: 36, padding: "0 12px" }} aria-label="Filter by trade">
          <option value="">All trades</option>
          {trades.map((t) => (
            <option key={t} value={t}>{titleCase(t)}</option>
          ))}
        </select>
      </div>

      {n && (
        <div className="metrics four">
          <div className="metric"><div className="label">Registered</div><div className="value num">{n.registered}</div><div className="caption">members with a Kaam account</div></div>
          <div className="metric"><div className="label">Active</div><div className="value num">{n.active}</div><div className="caption">had work in the last 30 days</div></div>
          <div className="metric"><div className="label">Available</div><div className="value num" style={{ color: "var(--green-d)" }}>{n.available}</div><div className="caption">reachable by the engine today</div></div>
          <div className="metric"><div className="label">Offline</div><div className="value num muted">{n.offline}</div><div className="caption">declared busy today</div></div>
        </div>
      )}

      {error && <div className="notice error">{error}</div>}

      <PendingWorkers onApproved={() => api.workers.list().then(setWorkers).catch(() => undefined)} />

      <div className="panel">
        <div className="stack" style={{ gap: 2 }}>
          <h2>Workload this week</h2>
          <div className="small muted">Limit {limit} jobs per worker per week. The engine pulls the quietest members forward.</div>
        </div>
        {!workers ? (
          <div className="small muted">Loading…</div>
        ) : (
          <div className="table">
            <div className="trow head t5">
              <span>Worker</span>
              <span className="hide-narrow">Trade</span>
              <span className="hide-narrow">Rating</span>
              <span>This week</span>
              <span className="hide-narrow">Status</span>
            </div>
            {rows.map((w) => {
              const pct = Math.min(100, Math.round((w.jobs_this_week / limit) * 100));
              const flag = pct >= 90 ? "overloaded" : w.jobs_this_week === 0 ? "free" : null;
              return (
                <div className="trow t5" key={w.id}>
                  <span className="stack" style={{ gap: 1 }}>
                    <span style={{ fontWeight: 700 }}>{w.name}</span>
                    <span className="tiny muted num">#{w.id}{w.phone ? ` · ${w.phone}` : ""}</span>
                  </span>
                  <span className="small hide-narrow">{titleCase(w.trade)}</span>
                  <span className="row small hide-narrow" style={{ gap: 4 }}>
                    <Star size={13} filled style={{ color: "var(--terracotta)" }} />
                    {w.rating === null ? "new" : w.rating.toFixed(1)}
                  </span>
                  <span className="row" style={{ gap: 10 }}>
                    <div className="bar" style={{ width: 90 }}>
                      <div style={{ width: `${pct}%`, background: flag === "overloaded" ? "var(--terracotta)" : "var(--accent)" }} />
                    </div>
                    <span className="num small" style={{ fontWeight: 700 }}>{w.jobs_this_week} / {limit}</span>
                  </span>
                  <span className="hide-narrow">
                    {flag === "overloaded" && <span className="pill terracotta">Overloaded</span>}
                    {flag === "free" && <span className="pill green">Free this week</span>}
                    {!flag && <span className="pill grey">Balanced</span>}
                  </span>
                </div>
              );
            })}
            {rows.length === 0 && <div className="small muted">No workers for this trade yet.</div>}
          </div>
        )}
      </div>
    </div>
  );
}
