/**
 * Worker onboarding: the page a brand-new Kaam worker lands on after signing up,
 * before the council approves their account. The worker cannot see jobs or
 * appear in the allocation engine until `worker_status` becomes "active".
 *
 * The council cannot activate anyone until a *verified* Aadhaar is on file
 * (app/routers/kaam.py), and /kaam/profile is unreachable while the worker is
 * pending (lib/auth.tsx redirects every other Kaam route here). So the upload
 * has to live on this page — otherwise onboarding deadlocks.
 */
import { useCallback, useEffect, useState } from "react";

import { api, errorMessage, type WorkerDocument } from "../../api";
import { Lock, Refresh, ShieldCheck } from "../../components/Icons";
import { useAuth } from "../../lib/auth";

export default function VerificationPending() {
  const { user, refresh } = useAuth();
  const [polling, setPolling] = useState(false);
  const [docs, setDocs] = useState<WorkerDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const workerId = user?.worker_id ?? null;
  const worker = user?.worker_id ? `worker #${user.worker_id}` : "your worker account";

  const loadDocs = useCallback(async () => {
    if (workerId === null) return;
    setLoadingDocs(true);
    try {
      setDocs(await api.workers.documents.list(workerId));
    } catch (e) {
      console.error(errorMessage(e));
      setDocs([]);
    } finally {
      setLoadingDocs(false);
    }
  }, [workerId]);

  useEffect(() => {
    void loadDocs();
  }, [loadDocs]);

  const aadhaar = docs.find((d) => d.document_type === "aadhaar");
  const uploaded = aadhaar && !aadhaar.rejection_reason;
  const verified = aadhaar?.verified === true;

  const recheck = async () => {
    setPolling(true);
    try {
      await refresh();
      await loadDocs();
    } catch (e) {
      console.error(errorMessage(e));
    } finally {
      setPolling(false);
    }
  };

  const details = [
    { icon: <ShieldCheck size={20} />, label: user?.name ?? "—", hint: "Name" },
    { icon: <Lock size={20} />, label: user?.phone ?? "—", hint: "Phone number" },
    { icon: <Lock size={20} />, label: user?.worker_id ?? "—", hint: "Worker ID" },
  ];

  return (
    <div className="page wide kaam-page">
      <header className="stack" style={{ gap: 6, marginBottom: 24 }}>
        <h1>Account under review</h1>
        <div className="small muted">Two short steps: upload your Aadhaar, then the council verifies it.</div>
      </header>

      <section className="card" style={{ maxWidth: 520, margin: "0 auto" }}>
        <div className="row" style={{ gap: 16, alignItems: "center", justifyContent: "center" }}>
          <div className="avatar" style={{ width: 56, height: 56 }}>
            {(user?.name ?? worker).slice(0, 2).toUpperCase()}
          </div>
        </div>
        <div className="stack" style={{ gap: 8, marginTop: 12 }}>
          {details.map((d) => (
            <div key={d.hint} className="row between">
              <span className="small muted">{d.hint}</span>
              <span className="small">{d.label}</span>
            </div>
          ))}
        </div>

        {workerId !== null ? (
          <div className="stack" style={{ gap: 10, marginTop: 20 }}>
            <h2 style={{ margin: 0, fontSize: 17 }}>1 · Upload your Aadhaar</h2>
            <div className="small muted">
              {verified
                ? "✓ Your Aadhaar is verified. The council is checking your account now."
                : uploaded
                  ? "Your Aadhaar is with the council. They mark it verified, then approve you."
                  : "The council can only approve you once an Aadhaar is on file and verified. Add it below."}
            </div>
            <UploadSection workerId={workerId} docs={docs} onAdded={loadDocs} />
          </div>
        ) : (
          <div className="notice" style={{ marginTop: 16 }}>
            This account is not linked to a worker record yet, so documents cannot be uploaded. Ask
            the council to re-check your account.
          </div>
        )}

        <div className="notice" style={{ marginTop: 16 }}>
          {verified
            ? "You’ll get jobs as soon as the council approves your account. Use Re-check status below."
            : "You’ll get jobs once the council approves your account. That usually takes a few minutes."}
        </div>

        <div className="row" style={{ gap: 12, marginTop: 16, justifyContent: "center" }}>
          <button type="button" className="btn" onClick={recheck} disabled={polling}>
            {polling ? <Refresh size={16} /> : "2 · Re-check status"}
          </button>
          <button type="button" className="btn outline" onClick={() => void api.auth.logout()}>
            Sign in as someone else
          </button>
        </div>
        {loadingDocs && <div className="small muted" style={{ marginTop: 8, textAlign: "center" }}>Loading documents…</div>}
      </section>
    </div>
  );
}

function UploadSection({
  workerId,
  docs,
  onAdded,
}: {
  workerId: number;
  docs: WorkerDocument[];
  onAdded: () => void | Promise<void>;
}) {
  const [type, setType] = useState("aadhaar");
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSaving(true);
    try {
      await api.workers.documents.add(workerId, { document_type: type, file_url: url });
      setUrl("");
      await onAdded();
    } catch (err) {
      alert(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <form className="row" style={{ gap: 8, alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={add}>
        <select className="chip" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="aadhaar">Aadhaar (required for approval)</option>
          <option value="id_proof">ID proof</option>
          <option value="insurance">Insurance</option>
          <option value="vehicle">Vehicle registration</option>
          <option value="other">Other</option>
        </select>
        <input
          className="input grow"
          placeholder="File URL (from your uploads)"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button className="chip" type="submit" disabled={saving || !url.trim()}>
          {saving ? "Adding…" : "Add"}
        </button>
      </form>
      {docs.length === 0 ? (
        <div className="small muted">No documents on file yet.</div>
      ) : (
        docs.map((d) => (
          <div key={d.id} className="row between" style={{ padding: "4px 0", gap: 12, flexWrap: "wrap" }}>
            <span className="small">
              {d.document_type} · <a href={d.file_url} target="_blank" rel="noreferrer">{d.file_url}</a>
            </span>
            <span
              className="small"
              style={{ color: d.verified ? "var(--green-d)" : d.rejection_reason ? "var(--red)" : undefined }}
            >
              {d.verified ? "✓ verified by the council" : d.rejection_reason ? `✗ rejected: ${d.rejection_reason}` : "· pending council review"}
            </span>
          </div>
        ))
      )}
    </div>
  );
}
