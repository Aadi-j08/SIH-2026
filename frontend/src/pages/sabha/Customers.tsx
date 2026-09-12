/** Households with a Ghar account, and how often they come back. */
import { useEffect, useState } from "react";

import { api, errorMessage, type CustomerRow } from "../../api";

function when(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso.replace(" ", "T") + "Z").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export default function Customers() {
  const [rows, setRows] = useState<CustomerRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.admin.customers().then(setRows).catch((e) => setError(errorMessage(e)));
  }, []);

  const shown = (rows ?? []).filter((r) => !q || r.name.toLowerCase().includes(q.toLowerCase()) || (r.locality ?? "").toLowerCase().includes(q.toLowerCase()) || r.phone.includes(q));
  const repeat = rows ? rows.filter((r) => r.bookings >= 2).length : 0;

  return (
    <div className="page wide sabha-page">
      <div className="row between" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div className="stack" style={{ gap: 4 }}>
          <h1 style={{ fontSize: 28 }}>Customers</h1>
          <div className="sub">{rows ? `${rows.length} households · ${repeat} have booked more than once` : "Loading…"}</div>
        </div>
        <label className="field" style={{ minHeight: 40, width: 260 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, area or phone" aria-label="Search customers" style={{ height: 36 }} />
        </label>
      </div>
      {error && <div className="notice error">{error}</div>}
      <div className="panel">
        <div className="table">
          <div className="trow head t5">
            <span>Household</span>
            <span className="hide-narrow">Area</span>
            <span>Bookings</span>
            <span className="hide-narrow">Completed</span>
            <span className="hide-narrow">Last booking</span>
          </div>
          {shown.map((r) => (
            <div className="trow t5" key={r.id}>
              <span className="stack" style={{ gap: 1 }}>
                <span style={{ fontWeight: 700 }}>{r.name}</span>
                <span className="tiny muted num">+91 {r.phone}</span>
              </span>
              <span className="small hide-narrow">{r.locality ?? "—"}</span>
              <span className="num">
                {r.bookings}
                {r.bookings >= 2 && <span className="pill indigo" style={{ marginLeft: 8 }}>Repeat</span>}
              </span>
              <span className="num hide-narrow">{r.completed}</span>
              <span className="small num hide-narrow">{when(r.last_booking_at)}</span>
            </div>
          ))}
          {rows && shown.length === 0 && <div className="small muted">No households match.</div>}
        </div>
      </div>
    </div>
  );
}
