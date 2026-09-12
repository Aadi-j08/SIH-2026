/** Reports & insights: the 7-day demand forecast per trade, against the workers actually available. */
import { useEffect, useState } from "react";

import { api, errorMessage, titleCase, type Forecast, type StaffingForecast } from "../../api";
import { TrendingUp } from "../../components/Icons";
import { useSabha } from "../../components/SabhaShell";
import { ForecastChart } from "./Demands";

export default function Reports() {
  const { overview } = useSabha();
  const trades = overview?.trades.map((t) => t.trade) ?? [];
  const [trade, setTrade] = useState<string>("");
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [staffing, setStaffing] = useState<StaffingForecast | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!trade && trades.length) setTrade(overview?.forecast_insight.trade ?? trades[0]);
  }, [trades, trade, overview]);

  useEffect(() => {
    if (!trade) return;
    Promise.all([api.forecast(trade, 7), api.staffing(trade, 7)])
      .then(([f, s]) => {
        setForecast(f);
        setStaffing(s);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [trade]);

  const insight = overview?.forecast_insight;

  return (
    <div className="page wide sabha-page">
      <div className="row between" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div className="stack" style={{ gap: 4 }}>
          <h1 style={{ fontSize: 28 }}>Reports &amp; insights</h1>
          <div className="sub">Plan next week’s workforce from what the last four weeks looked like</div>
        </div>
        <select value={trade} onChange={(e) => setTrade(e.target.value)} className="chip" style={{ minHeight: 36, padding: "0 12px" }} aria-label="Trade">
          {trades.map((t) => (
            <option key={t} value={t}>{titleCase(t)}</option>
          ))}
        </select>
      </div>
      {error && <div className="notice error">{error}</div>}
      <div className="sabha-grid">
        <div className="panel">
          <div className="stack" style={{ gap: 2 }}>
            <h2>Demand forecast · {trade ? titleCase(trade) : ""}</h2>
            <div className="small muted">Expected bookings per day, next 7 days</div>
          </div>
          {forecast ? <ForecastChart forecast={forecast} /> : <div className="small muted">Loading…</div>}
        </div>
        <div className="stack-lg">
          {insight && (
            <div className="panel">
              <div className="row" style={{ gap: 8 }}>
                <TrendingUp size={18} style={{ color: "var(--indigo-d)" }} />
                <h2>AI insight</h2>
              </div>
              <div className="insight">{insight.text}</div>
            </div>
          )}
          {staffing && (
            <div className="panel">
              <div className="stack" style={{ gap: 2 }}>
                <h2>Workforce capacity · {titleCase(staffing.trade)}</h2>
                <div className="small muted">Workers needed vs members not declared busy, day by day</div>
              </div>
              <div className="table">
                <div className="trow head t4">
                  <span>Day</span>
                  <span>Expected</span>
                  <span>Needed</span>
                  <span>Available</span>
                </div>
                {staffing.days.map((d) => (
                  <div className="trow t4" key={d.date}>
                    <span style={{ fontWeight: 600 }}>{d.weekday.slice(0, 3)} <span className="tiny muted">{d.date.slice(5)}</span></span>
                    <span className="num">{d.expected_bookings.toFixed(1)}</span>
                    <span className="num">{d.workers_needed}</span>
                    <span className="num" style={{ color: d.shortage > 0 ? "var(--terracotta-d)" : "var(--green-d)", fontWeight: 700 }}>
                      {d.available_workers}{d.shortage > 0 ? ` (−${d.shortage})` : ""}
                    </span>
                  </div>
                ))}
              </div>
              <div className="small" style={{ color: staffing.shortage > 0 ? "var(--terracotta-d)" : "var(--ink-2)" }}>{staffing.recommendation}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
