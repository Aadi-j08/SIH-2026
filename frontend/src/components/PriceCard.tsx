import { useEffect, useState } from "react";
import { api, errorMessage, formatRupees } from "../api";
import { TrendingUp } from "./Icons";

export function PriceCard({ trade = "general", horizon = 7 }: { trade?: string; horizon?: number }) {
  const [bands, setBands] = useState<null | Array<{
    date: string; day_name: string; is_weekend: boolean;
    predicted_bookings: number; floor_rate_inr: number; recommended_rate_inr: number;
  }>>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!bands);

  useEffect(() => {
    let cancelled = false;
    api.dynamicPricing(trade, horizon).then((data) => {
      if (!cancelled) { setBands(data.price_bands); setErr(null); }
    }).catch((e: unknown) => { if (!cancelled) setErr(errorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [trade, horizon]);

  return (
    <section className="panel" aria-labelledby="price-h">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="stack" style={{ gap: 2 }}>
          <h2 id="price-h">Dynamic fair-wage pricing</h2>
          <div className="small muted">Ridge forecast · floor is the guaranteed minimum wage</div>
        </div>
        <span className="small monospace">{trade}</span>
      </div>
      {err && <div className="notice error">{err}</div>}
      {loading && <div className="small muted">Loading price bands…</div>}
      {!loading && bands && (
        <table className="small" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left" }}>
              <th>Date</th><th>Bookings</th><th>Min wage floor</th><th>Recommended</th>
            </tr>
          </thead>
          <tbody>
            {bands.map((b) => (
              <tr key={b.date}>
                <td>{b.day_name} {b.date.slice(5)}</td>
                <td>{b.predicted_bookings}</td>
                <td>{formatRupees(b.floor_rate_inr)}</td>
                <td>{formatRupees(b.recommended_rate_inr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!loading && !bands && !err && <div className="small muted">No pricing data.</div>}
      <div className="insight" style={{ marginTop: 8, gap: 6 }}>
        <TrendingUp size={16} style={{ color: "var(--indigo-d)" }} />
        <span>Weekend surges apply automatically; floor never drops below the living wage.</span>
      </div>
    </section>
  );
}
