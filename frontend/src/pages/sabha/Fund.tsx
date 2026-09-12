/** The cooperative fund: how much there is, how it is allocated, and the council's lever to change the policy. */
import { useEffect, useState, type FormEvent } from "react";

import { api, errorMessage, formatRupees } from "../../api";
import { FundPie } from "../../components/sabha/FundPie";
import { useSabha } from "../../components/SabhaShell";

export default function Fund() {
  const { overview, reload } = useSabha();
  const [draft, setDraft] = useState<Record<string, number> | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (overview && !draft) setDraft({ ...overview.metrics.fund.allocation });
  }, [overview, draft]);

  if (!overview || !draft) return <div className="page wide muted">Loading…</div>;
  const f = overview.metrics.fund;
  const sum = Object.values(draft).reduce((a, b) => a + b, 0);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      await api.cooperative.update({ fund_allocation: draft });
      await reload();
      setNote({ kind: "info", text: "Allocation updated. It applies to the fund from now on and shows on the overview." });
    } catch (err) {
      setNote({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wide sabha-page">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ fontSize: 28 }}>Cooperative fund</h1>
        <div className="sub">10% of every bill goes here. The general body decides how it is used; the council applies it.</div>
      </div>
      <div className="metrics four">
        <div className="metric"><div className="label">In the fund</div><div className="value num">{formatRupees(f.total_rupees)}</div><div className="caption">since the cooperative started</div></div>
        <div className="metric"><div className="label">Added this month</div><div className="value num" style={{ color: "var(--green-d)" }}>+{formatRupees(f.this_month_rupees)}</div><div className="caption">from completed jobs</div></div>
        <div className="metric"><div className="label">Worker welfare share</div><div className="value num">{formatRupees((f.total_rupees * (f.allocation["Worker welfare"] ?? 0)) / 100)}</div><div className="caption">{f.allocation["Worker welfare"] ?? 0}% of the fund</div></div>
        <div className="metric"><div className="label">Categories</div><div className="value num">{Object.keys(f.allocation).length}</div><div className="caption">allocation heads</div></div>
      </div>
      <div className="sabha-grid">
        <div className="panel">
          <div className="stack" style={{ gap: 2 }}>
            <h2>Current allocation</h2>
            <div className="small muted">Transparent and collective — every member sees the same pie</div>
          </div>
          <FundPie allocation={f.allocation} total={f.total_rupees} size={200} />
        </div>
        <form className="panel" onSubmit={save}>
          <div className="stack" style={{ gap: 2 }}>
            <h2>Change the allocation</h2>
            <div className="small muted">Percentages must add up to 100. Record the general-body resolution before changing it.</div>
          </div>
          <div className="stack">
            {Object.entries(draft).map(([name, pct]) => (
              <label className="row" key={name} style={{ gap: 12 }}>
                <span className="grow small" style={{ fontWeight: 600 }}>{name}</span>
                <span className="field" style={{ minHeight: 40, width: 110 }}>
                  <input type="number" min={0} max={100} value={pct} onChange={(e) => setDraft({ ...draft, [name]: Number(e.target.value) })} aria-label={`${name} percent`} style={{ height: 36, textAlign: "right" }} />
                  <span className="muted">%</span>
                </span>
              </label>
            ))}
          </div>
          <div className="row between">
            <span className={`small ${sum === 100 ? "muted" : ""}`} style={{ color: sum === 100 ? undefined : "var(--terracotta-d)", fontWeight: 600 }}>
              Total {sum}%{sum !== 100 ? " — must be 100" : ""}
            </span>
            <button type="submit" className="btn small primary" disabled={busy || sum !== 100}>
              {busy ? "Saving…" : "Save allocation"}
            </button>
          </div>
          {note && <div className={`notice ${note.kind}`}>{note.text}</div>}
        </form>
      </div>
    </div>
  );
}
