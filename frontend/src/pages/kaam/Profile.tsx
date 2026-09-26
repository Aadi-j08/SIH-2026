/** Kaam worker profile: a worker's own skills, certificates, portfolio and documents. Council members see verification toggles too. */
import { useCallback, useEffect, useState } from "react";

import {
  api,
  errorMessage,
   type Certification,
  type Grievance,
  type ProfileSummary,
  type PortfolioItem,
  type Skill,
  type SkillLevel,
  type WorkerDocument,
} from "../../api";
import { Check, Star } from "../../components/Icons";
import { useAuth } from "../../lib/auth";

type Tab = "skills" | "certifications" | "portfolio" | "documents";

export default function WorkerProfile() {
  const { user } = useAuth();
  const workerId = user?.worker_id ?? null;
  const isCouncil = user?.is_council ?? false;

  const [profile, setProfile] = useState<ProfileSummary | null>(null);
  const [tab, setTab] = useState<Tab>("skills");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (workerId === null) return;
    try {
      const p = await api.workers.profile(workerId);
      setProfile(p);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [workerId]);

  useEffect(() => {
    void load();
  }, [load]);

  const refresh = () => void load();

  if (workerId === null) return <div className="page notice error">This account is not linked to a worker record.</div>;
  if (!profile) return <div className="page muted">{error ? <div className="notice error">{error}</div> : "Loading…"}</div>;

  const pct = Math.round((profile.completeness ?? 0) * 100);

  return (
    <div className="page wide">
      <div className="stack" style={{ gap: 6 }}>
        <h1 style={{ fontSize: 28, margin: 0 }}>My profile</h1>
        <div className="sub">How your skills, certificates and work look to the cooperative and customers.</div>
        <div className="row small" style={{ gap: 8, alignItems: "center" }}>
          <Star filled={pct >= 80} />
          <span>Profile strength: {pct}%</span>
        </div>
      </div>

      <div className="tabs" style={{ gap: 4, flexWrap: "wrap" }}>
        {(["skills", "certifications", "portfolio", "documents"] as Tab[]).map((t) => (
          <button
            key={t}
            className={`chip ${tab === t ? "on" : ""}`}
            onClick={() => setTab(t)}
            style={{ textTransform: "capitalize" }}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <div className="notice error">{error}</div>}

      {tab === "skills" && <SkillsSection workerId={workerId} skills={profile.skills} isCouncil={isCouncil} onSaved={refresh} />}
      {tab === "certifications" && <CertificatesSection workerId={workerId} certs={profile.certifications} isCouncil={isCouncil} onSaved={refresh} />}
      {tab === "portfolio" && <PortfolioSection workerId={workerId} items={profile.portfolio} isCouncil={isCouncil} onSaved={refresh} />}
      {tab === "documents" && <DocumentsSection workerId={workerId} docs={profile.documents} />}

      <hr style={{ margin: "24px 0", border: "none", borderTop: "1px solid var(--line)" }} />
      <GrievanceForm workerId={workerId} onRaised={() => {}} />
    </div>
  );
}

function GrievanceForm({ workerId }: { workerId: number; onRaised: () => void }) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<Grievance["kind"]>("other");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const { user } = useAuth();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !desc) return;
    setSaving(true);
    try {
      await api.welfare.raiseGrievance({ worker_id: user?.worker_id ?? workerId, kind, title, description: desc });
      setTitle(""); setDesc("");
      alert("Grievance raised for council review.");
    } catch (err) {
      alert(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card stack" style={{ gap: 8 }} onSubmit={submit}>
      <h2 style={{ fontSize: 18, margin: 0 }}>Raise a grievance</h2>
      <select className="chip" value={kind} onChange={(e) => setKind(e.target.value as Grievance["kind"])}>
        <option value="wage">Wage</option>
        <option value="safety">Safety</option>
        <option value="equipment">Equipment</option>
        <option value="assignment">Assignment</option>
        <option value="other">Other</option>
      </select>
      <input className="input" placeholder="Short title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea className="input" placeholder="Details" value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} />
      <button className="btn small primary" type="submit" disabled={saving || !title || !desc}>{saving ? "Raising…" : "Submit to council"}</button>
    </form>
  );
}

function SkillsSection({ workerId, skills, isCouncil, onSaved }: {
  workerId: number; skills: Skill[]; isCouncil: boolean; onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [level, setLevel] = useState<SkillLevel>("intermediate");
  const [saving, setSaving] = useState(false);

  const add = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.workers.skills.add(workerId, { name, level });
      setName(""); setLevel("intermediate");
      await onSaved();
    } catch (e) { alert(errorMessage(e)); } finally { setSaving(false); }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
        <input className="input" placeholder="Skill, e.g. tile" value={name} onChange={(e) => setName(e.target.value)} />
        <select className="chip" value={level} onChange={(e) => setLevel(e.target.value as SkillLevel)}>
          <option value="beginner">Beginner</option>
          <option value="intermediate">Intermediate</option>
          <option value="expert">Expert</option>
        </select>
        <button className="chip" onClick={add} disabled={saving || !name.trim()}>Add</button>
      </div>
      {skills.length === 0 && <div className="small muted">No skills yet.</div>}
      {skills.map((s) => (
        <div key={s.id} className="row between" style={{ padding: "4px 0" }}>
          <span>{s.name} · {s.level}{isCouncil && s.verified ? " ✓ verified" : ""}</span>
        </div>
      ))}
    </div>
  );
}

function CertificatesSection({ workerId, certs, isCouncil, onSaved }: {
  workerId: number; certs: Certification[]; isCouncil: boolean; onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const [issued, setIssued] = useState("");
  const [saving, setSaving] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.workers.certifications.add(workerId, { name, issuing_org: org || undefined, issue_date: issued || undefined });
      setName(""); setOrg(""); setIssued("");
      await onSaved();
    } catch (err) { alert(errorMessage(err)); } finally { setSaving(false); }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <form className="row" style={{ gap: 8, alignItems: "flex-end" }} onSubmit={add}>
        <input className="input" placeholder="Certificate name, e.g. Plumbing License" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input" placeholder="Issuing organisation" value={org} onChange={(e) => setOrg(e.target.value)} />
        <input className="input" type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />
        <button className="chip" type="submit" disabled={saving || !name.trim()}>Add</button>
      </form>
      {certs.length === 0 && <div className="small muted">No certificates added.</div>}
      {certs.map((c) => (
        <div key={c.id} className="row between" style={{ padding: "4px 0" }}>
          <span>{c.name}{c.issuing_org ? ` · ${c.issuing_org}` : ""}{c.issue_date ? ` (${c.issue_date})` : ""}</span>
          {isCouncil && (
            <button
              className={`chip ${c.verified ? "on" : ""}`}
              onClick={async () => {
                try { await api.workers.certifications.verify(workerId, c.id, !c.verified); await onSaved(); } catch (e) { alert(errorMessage(e)); } }}
              title={c.verified ? "Unverify" : "Verify"}
            >
              {c.verified ? <Check /> : "Verify"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function PortfolioSection({ workerId, items, isCouncil, onSaved }: {
  workerId: number; items: PortfolioItem[]; isCouncil: boolean; onSaved: () => void;
}) {
  const [url, setUrl] = useState("");
  const [caption, setCaption] = useState("");
  const [saving, setSaving] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSaving(true);
    try {
      await api.workers.portfolio.add(workerId, { image_url: url, caption: caption || undefined });
      setUrl(""); setCaption("");
      await onSaved();
    } catch (err) { alert(errorMessage(err)); } finally { setSaving(false); }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <form className="row" style={{ gap: 8, alignItems: "flex-end" }} onSubmit={add}>
        <input className="input" placeholder="Photo URL (from your uploads)" value={url} onChange={(e) => setUrl(e.target.value)} />
        <input className="input" placeholder="Caption" value={caption} onChange={(e) => setCaption(e.target.value)} />
        <button className="chip" type="submit" disabled={saving || !url.trim()}>Add</button>
      </form>
      {items.length === 0 && <div className="small muted">No portfolio items yet.</div>}
      <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
        {items.map((p) => (
          <div key={p.id} className="stack" style={{ gap: 4, alignItems: "center" }}>
            <img src={p.image_url} alt={p.caption ?? "portfolio"} style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 6, border: "1px solid var(--border)" }} />
            {isCouncil && (
              <button
                className={`chip ${p.verified ? "on" : ""}`}
                onClick={async () => { try { await api.workers.portfolio.verify(workerId, p.id, !p.verified); await onSaved(); } catch (e) { alert(errorMessage(e)); } }}
                title={p.verified ? "Unverify" : "Verify"}
              >
                {p.verified ? <Check /> : "Verify"}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function DocumentsSection({ workerId, docs }: { workerId: number; docs: WorkerDocument[] }) {
  const [type, setType] = useState("id_proof");
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSaving(true);
    try {
      await api.workers.documents.add(workerId, { document_type: type, file_url: url });
      setUrl("");
      alert("Document added");
    } catch (err) { alert(errorMessage(err)); } finally { setSaving(false); }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <form className="row" style={{ gap: 8, alignItems: "flex-end" }} onSubmit={add}>
        <select className="chip" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="id_proof">ID proof</option>
          <option value="insurance">Insurance</option>
          <option value="vehicle">Vehicle registration</option>
          <option value="other">Other</option>
        </select>
        <input className="input" placeholder="File URL (from your uploads)" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="chip" type="submit" disabled={saving || !url.trim()}>Add</button>
      </form>
      {docs.length === 0 && <div className="small muted">No documents on file.</div>}
      {docs.map((d) => (
        <div key={d.id} className="row between" style={{ padding: "4px 0" }}>
          <span>{d.document_type} · <a href={d.file_url}>{d.file_url}</a></span>
        </div>
      ))}
    </div>
  );
}
