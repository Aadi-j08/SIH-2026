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
import { useLocation } from "react-router-dom";

import {
  api, DOCUMENT_KIND_LABELS, errorMessage, UPLOAD_ACCEPT, UPLOAD_MAX_BYTES_LABEL,
  type DocumentKind, type WorkerDocument,
} from "../../api";
import { Lock, Refresh, ShieldCheck } from "../../components/Icons";
import { useAuth } from "../../lib/auth";
import { describeFile, validateDocumentFile } from "../../lib/uploads";

export default function VerificationPending() {
  const { user, refresh } = useAuth();
  const location = useLocation();
  // Sign-up hands the worker over here when its upload failed, carrying the reason.
  const carriedError = (location.state as { uploadError?: string } | null)?.uploadError ?? null;
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
            {carriedError && <div className="notice error">Your Aadhaar did not upload: {carriedError}</div>}
            <UploadSection workerId={workerId} docs={docs} onAdded={loadDocs} />
          </div>
        ) : (
          <div className="notice" style={{ marginTop: 16 }}>
            This account is not linked to a worker record yet, so documents cannot be uploaded. Ask
            the council to re-check your account.
          </div>
        )}

        {user?.worker_status === "rejected" ? (
          <div className="notice error" style={{ marginTop: 16 }}>
            <strong>The council did not approve this account.</strong> Your uploaded documents are still on
            file, but no jobs are offered to a rejected applicant. Speak to the council office to find out
            what is missing and have the account reviewed again.
          </div>
        ) : (
          <div className="notice" style={{ marginTop: 16 }}>
            {verified
              ? "You’ll get jobs as soon as the council approves your account. Use Re-check status below."
              : "You’ll get jobs once the council approves your account. That usually takes a few minutes."}
          </div>
        )}

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
  const [type, setType] = useState<DocumentKind>("aadhaar");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (chosen: File | null) => {
    setFile(chosen);
    setError(null);
    setFileError(chosen ? validateDocumentFile(chosen) : null);
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || fileError) return;
    setSaving(true);
    setError(null);
    try {
      await api.workers.documents.upload(workerId, file, type);
      setFile(null);
      await onAdded();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <form className="stack" style={{ gap: 8 }} onSubmit={add}>
        <select
          className="chip"
          value={type}
          onChange={(e) => setType(e.target.value as DocumentKind)}
          aria-label="Document type"
          style={{ alignSelf: "flex-start" }}
        >
          {Object.entries(DOCUMENT_KIND_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <div className="stack" style={{ gap: 6 }}>
          <input
            type="file"
            accept={UPLOAD_ACCEPT}
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
            aria-label={`${DOCUMENT_KIND_LABELS[type] ?? type} file`}
            style={{ fontSize: 15 }}
          />
          <span className="tiny muted">PDF, JPG or PNG, up to {UPLOAD_MAX_BYTES_LABEL}.</span>
          {file && !fileError && (
            <span className="small" style={{ color: "var(--green-d)" }}>✓ {describeFile(file)}</span>
          )}
        </div>
        {fileError && <div className="notice error">{fileError}</div>}
        {error && <div className="notice error">{error}</div>}
        <button className="chip" type="submit" disabled={saving || !file || !!fileError} style={{ alignSelf: "flex-start" }}>
          {saving ? "Uploading…" : "Add document"}
        </button>
      </form>
      {docs.length === 0 ? (
        <div className="small muted">No documents on file yet.</div>
      ) : (
        docs.map((d) => (
          <div key={d.id} className="row between" style={{ padding: "4px 0", gap: 12, flexWrap: "wrap" }}>
            <span className="small">
              {DOCUMENT_KIND_LABELS[d.document_type] ?? d.document_type}
              {d.has_content && d.filename ? ` · ${d.filename}` : ""}
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
