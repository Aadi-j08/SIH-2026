/** Payments: every completed job split 85 / 10 / 5, and what each member has earned. */
import { useEffect, useState } from "react";

import { api, errorMessage, formatRupees, type Dashboard } from "../../api";
import { MoneySplit } from "./Demands";

export default function Payments() {
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.admin.dashboard().then(setDash).catch((e) => setError(errorMessage(e)));
  }, []);

  const workers = (dash?.workers ?? []).filter((w) => w.completed_jobs > 0).sort((a, b) => b.earnings_rupees - a.earnings_rupees);

  return (
    <div className="page wide sabha-page">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ fontSize: 28 }}>Payments</h1>
        <div className="sub">Paid after the job, split to the paisa, open to everyone in the cooperative</div>
      </div>
      {error && <div className="notice error">{error}</div>}
      {dash && (
        <>
          <div className="metrics four">
            <div className="metric"><div className="label">Billed to date</div><div className="value num">{formatRupees(dash.money.gross_rupees)}</div><div className="caption">across {dash.bookings.completed} completed jobs</div></div>
            <div className="metric"><div className="label">Paid to workers</div><div className="value num" style={{ color: "var(--green-d)" }}>{formatRupees(dash.money.worker_payouts_rupees)}</div><div className="caption">85% of every bill</div></div>
            <div className="metric"><div className="label">Cooperative fund</div><div className="value num">{formatRupees(dash.money.welfare_fund_rupees)}</div><div className="caption">10% of every bill</div></div>
            <div className="metric"><div className="label">Platform operations</div><div className="value num muted">{formatRupees(dash.money.platform_operations_rupees)}</div><div className="caption">5% of every bill</div></div>
          </div>
          <div className="sabha-grid">
            <div className="panel">
              <div className="stack" style={{ gap: 2 }}>
                <h2>The split</h2>
                <div className="small muted">Fixed by the general body; the ledger applies it automatically</div>
              </div>
              <MoneySplit dashboard={dash} />
            </div>
            <div className="panel">
              <div className="stack" style={{ gap: 2 }}>
                <h2>Earnings by member</h2>
                <div className="small muted">Completed jobs, earnings and days of engagement toward benefits</div>
              </div>
              <div className="table">
                <div className="trow head t4">
                  <span>Worker</span>
                  <span>Jobs</span>
                  <span>Earned</span>
                  <span className="hide-narrow">Days</span>
                </div>
                {workers.map((w) => (
                  <div className="trow t4" key={w.id}>
                    <span style={{ fontWeight: 700 }}>{w.name ?? `Worker ${w.id}`}</span>
                    <span className="num">{w.completed_jobs}</span>
                    <span className="num" style={{ fontWeight: 700 }}>{formatRupees(w.earnings_rupees)}</span>
                    <span className="num small muted hide-narrow">{w.engagement_days} / 90</span>
                  </div>
                ))}
                {workers.length === 0 && <div className="small muted">No completed jobs yet.</div>}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
