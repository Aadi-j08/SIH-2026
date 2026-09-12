/** Settings: the levers the dashboard applies everywhere, plus how new council members get in. */
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage } from "../../api";
import { Lock } from "../../components/Icons";
import { useSabha } from "../../components/SabhaShell";
import { useAuth } from "../../lib/auth";

export default function Settings() {
  const { overview, reload } = useSabha();
  const { user } = useAuth();
  const [limit, setLimit] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (overview && limit === "") setLimit(overview.profile.weekly_job_limit);
  }, [overview, limit]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (limit === "") return;
    setBusy(true);
    setNote(null);
    try {
      await api.cooperative.update({ weekly_job_limit: Number(limit) });
      await reload();
      setNote({ kind: "info", text: "Saved. Workload percentages and “nearing limit” warnings use the new limit." });
    } catch (err) {
      setNote({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wide sabha-page">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ fontSize: 28 }}>Settings</h1>
        <div className="sub">Policies the council applies, and access to Sabha</div>
      </div>
      {note && <div className={`notice ${note.kind}`}>{note.text}</div>}
      <div className="sabha-grid">
        <form className="panel" onSubmit={save}>
          <div className="stack" style={{ gap: 2 }}>
            <h2>Fair workload</h2>
            <div className="small muted">The most jobs one member should take in a week. Drives the workload bars, the “nearing limit” alert and who counts as available.</div>
          </div>
          <label className="row" style={{ gap: 12 }}>
            <span className="grow small" style={{ fontWeight: 600 }}>Weekly job limit per worker</span>
            <span className="field" style={{ minHeight: 40, width: 110 }}>
              <input type="number" min={1} max={50} value={limit} onChange={(e) => setLimit(e.target.value === "" ? "" : Number(e.target.value))} aria-label="Weekly job limit" style={{ height: 36, textAlign: "right" }} />
              <span className="muted small">jobs</span>
            </span>
          </label>
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button type="submit" className="btn small primary" disabled={busy || limit === ""}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </form>
        <div className="panel">
          <div className="stack" style={{ gap: 2 }}>
            <h2>Fund allocation</h2>
            <div className="small muted">How the 10% cooperative fund is used. Changed on the fund page after a general-body resolution.</div>
          </div>
          <Link to="/sabha/fund" className="btn small outline" style={{ alignSelf: "flex-start" }}>Open the fund</Link>
        </div>
        <div className="panel">
          <div className="row" style={{ gap: 8 }}>
            <Lock size={18} style={{ color: "var(--ink-2)" }} />
            <h2>Council access</h2>
          </div>
          <p className="small" style={{ margin: 0, lineHeight: 1.55, color: "var(--ink-2)" }}>
            New council members create a Sabha account with the cooperative’s council code. The code is set on the server
            (<code>SAHAKARSETU_COUNCIL_CODE</code>, several codes may be comma-separated) and is never shown here — share it offline.
          </p>
          <div className="small muted">Signed in as {user?.name}{user?.role ? ` · ${user.role}` : ""} · +91 {user?.phone}</div>
        </div>
      </div>
    </div>
  );
}
