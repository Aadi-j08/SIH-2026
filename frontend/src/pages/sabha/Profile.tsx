/** Sabha profile: who the cooperative is, who belongs to it, how it is verified and governed. Editable by the council. */
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, errorMessage, titleCase, type Cooperative, type CooperativeUpdate } from "../../api";
import { Check, MapPin, ShieldCheck } from "../../components/Icons";
import { useSabha } from "../../components/SabhaShell";

type Counts = { total: number; workers: number; customers: number; council: number };

export default function Profile() {
  const { overview, reload } = useSabha();
  const [coop, setCoop] = useState<Cooperative | null>(null);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<CooperativeUpdate>({});
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  useEffect(() => {
    api.cooperative.get().then(setCoop).catch((e) => setNote({ kind: "error", text: errorMessage(e) }));
    Promise.all([api.workers.list(), api.admin.customers()])
      .then(([w, c]) => {
        const total = overview?.cooperative.members ?? w.length + c.length;
        setCounts({ total, workers: w.length, customers: c.length, council: Math.max(0, total - w.length - c.length) });
      })
      .catch(() => setCounts(null));
  }, [overview?.cooperative.members]);

  if (!coop) return <div className="page wide muted">Loading…</div>;

  const startEdit = () => {
    setDraft({
      name: coop.name, short_name: coop.short_name, registration_id: coop.registration_id ?? "", established: coop.established ?? undefined,
      area: coop.area ?? "", radius_km: coop.radius_km ?? undefined, secretary: coop.secretary ?? "", coordinator: coop.coordinator ?? "",
      last_meeting: coop.last_meeting ?? "",
    });
    setEditing(true);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      const body: CooperativeUpdate = {};
      for (const [k, v] of Object.entries(draft)) if (v !== "" && v !== undefined) (body as Record<string, unknown>)[k] = v;
      setCoop(await api.cooperative.update(body));
      await reload();
      setEditing(false);
      setNote({ kind: "info", text: "Profile updated." });
    } catch (err) {
      setNote({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const services = overview?.trades.map((t) => t.trade) ?? [];
  const field = (label: string, key: keyof CooperativeUpdate, type: "text" | "number" | "date" = "text") => (
    <label className="stack" style={{ gap: 4 }} key={key}>
      <span className="label">{label}</span>
      <span className="field" style={{ minHeight: 40 }}>
        <input
          type={type}
          value={(draft[key] as string | number | undefined) ?? ""}
          onChange={(e) => setDraft({ ...draft, [key]: type === "number" ? (e.target.value === "" ? undefined : Number(e.target.value)) : e.target.value })}
          style={{ height: 36 }}
        />
      </span>
    </label>
  );

  return (
    <div className="page wide sabha-page">
      <div className="row between" style={{ alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div className="stack" style={{ gap: 6 }}>
          <div className="label">Sabha profile</div>
          <h1 style={{ fontSize: 28 }}>{coop.name}</h1>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            {coop.verified && <span className="pill green" style={{ gap: 5 }}><ShieldCheck size={13} /> Verified Cooperative</span>}
            {coop.area && <span className="row small muted" style={{ gap: 4 }}><MapPin size={14} /> {coop.area}{coop.radius_km ? ` — ${coop.radius_km} km radius` : ""}</span>}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {!editing && <button type="button" className="btn small outline" onClick={startEdit}>Edit profile</button>}
          <Link to="/sabha/workers" className="btn small primary">Manage members</Link>
        </div>
      </div>
      {note && <div className={`notice ${note.kind}`}>{note.text}</div>}

      {editing ? (
        <form className="panel" onSubmit={save}>
          <h2>Edit profile</h2>
          <div className="grid-2" style={{ gap: 14 }}>
            {field("Cooperative name", "name")}
            {field("Short name (header)", "short_name")}
            {field("Registration ID", "registration_id")}
            {field("Established (year)", "established", "number")}
            {field("Operating area", "area")}
            {field("Radius (km)", "radius_km", "number")}
            {field("Secretary", "secretary")}
            {field("Coordinator", "coordinator")}
            {field("Last general meeting", "last_meeting", "date")}
          </div>
          <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
            <button type="button" className="btn small outline" onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
            <button type="submit" className="btn small primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </form>
      ) : (
        <div className="sabha-grid">
          <div className="panel">
            <h2>Registration</h2>
            <dl className="kv">
              <div><dt>Registration ID</dt><dd className="num">{coop.registration_id ?? "—"}</dd></div>
              <div><dt>Established</dt><dd className="num">{coop.established ?? "—"}</dd></div>
              <div><dt>Operating area</dt><dd>{coop.area ?? "—"}{coop.radius_km ? ` — ${coop.radius_km} km radius` : ""}</dd></div>
            </dl>
            <h2 style={{ marginTop: 6 }}>Services</h2>
            <div className="chips">
              {services.map((s) => (
                <span className="chip" key={s} style={{ minHeight: 36 }}>{titleCase(s)}</span>
              ))}
              {services.length === 0 && <span className="small muted">No trades registered yet.</span>}
            </div>
          </div>
          <div className="panel">
            <h2>Members</h2>
            <dl className="kv">
              <div><dt>Total members</dt><dd className="num">{counts?.total ?? "—"}</dd></div>
              <div><dt>Service workers</dt><dd className="num">{counts?.workers ?? "—"}</dd></div>
              <div><dt>Customers</dt><dd className="num">{counts?.customers ?? "—"}</dd></div>
              <div><dt>Cooperative / admin members</dt><dd className="num">{counts?.council ?? "—"}</dd></div>
            </dl>
          </div>
          <div className="panel">
            <h2>Verification</h2>
            <ul className="check-list">
              <li className={coop.verified ? "on" : ""}><Check size={16} /> Cooperative verified</li>
              <li className={coop.worker_kyc ? "on" : ""}><Check size={16} /> Worker KYC</li>
              <li className={coop.payments_verified ? "on" : ""}><Check size={16} /> Payment system verified</li>
            </ul>
          </div>
          <div className="panel">
            <h2>Governance</h2>
            <dl className="kv">
              <div><dt>Secretary</dt><dd>{coop.secretary ?? "—"}</dd></div>
              <div><dt>Coordinator</dt><dd>{coop.coordinator ?? "—"}</dd></div>
              <div><dt>Last general meeting</dt><dd className="num">{coop.last_meeting ? new Date(coop.last_meeting).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—"}</dd></div>
              <div><dt>Weekly job limit</dt><dd className="num">{coop.weekly_job_limit} per worker</dd></div>
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
