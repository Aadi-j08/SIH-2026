/**
 * Worker onboarding: the page a brand-new Kaam worker lands on after signing up,
 * before the council approves their account. The worker cannot see jobs or
 * appear in the allocation engine until `worker_status` becomes "active".
 *
 * The council cannot activate anyone until a *verified* Aadhaar is on file
 * (app/routers/kaam.py), and /kaam/profile is unreachable while the worker is
 * pending (lib/auth.tsx redirects every other Kaam route here). So the upload
 * has to live on this page — otherwise onboarding deadlocks.
 *
 * Layout is a two-column `sabha-grid` that collapses to one column under
 * 1100px (styles.css), so the account summary and the uploader sit side by side
 * on a desktop and stack on a phone.
 */
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import {
  api, DOCUMENT_KIND_LABELS, errorMessage, UPLOAD_ACCEPT, UPLOAD_MAX_BYTES_LABEL,
  type DocumentKind, type WorkerDocument,
} from "../../api";
import { Check, Cross, Lock, Refresh, ShieldCheck } from "../../components/Icons";
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
  const rejected = user?.worker_status === "rejected";

  // One fetcher, one effect. An earlier revision of this page also declared a
  // `loadDocuments` + effect pair alongside these, which listed documents twice
  // on every mount; keep this as the single source.
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
    <div className="page wide kaam-page" style={{ maxWidth: 980, margin: "0 auto" }}>
      <header className="stack" style={{ gap: 6, marginBottom: 20 }}>
        <h1>Account under review</h1>
        <div className="small muted">Two short steps: upload your Aadhaar, then the council verifies it.</div>
      </header>

      <div className="sabha-grid" style={{ gap: 16 }}>
        {/* Account summary */}
        <section className="card stack" style={{ gap: 14 }}>
          <div className="row" style={{ gap: 16, alignItems: "center" }}>
            <div className="avatar" style={{ width: 56, height: 56, fontSize: 20 }}>
              {(user?.name ?? worker).slice(0, 2).toUpperCase()}
            </div>
            <div className="stack" style={{ gap: 2, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{user?.name ?? worker}</div>
              <div className="tiny muted">
                {rejected ? "Rejected by the council" : verified ? "Aadhaar verified — awaiting approval" : "Pending council review"}
              </div>
            </div>
          </div>

          <div className="stack" style={{ gap: 8 }}>
            {details.map((d) => (
              <div
                key={d.hint}
                className="row between small"
                style={{ borderBottom: "1px solid var(--line-soft)", paddingBottom: 6, gap: 12 }}
              >
                <span className="muted">{d.hint}</span>
                <span style={{ fontWeight: 600, wordBreak: "break-word", textAlign: "right" }}>{d.label}</span>
              </div>
            ))}
          </div>

          {rejected ? (
            <div className="notice error">
              <strong>The council did not approve this account.</strong> Your uploaded documents are still on
              file, but no jobs are offered to a rejected applicant. Speak to the council office to find out
              what is missing and have the account reviewed again.
            </div>
          ) : (
            <div className="notice">
              {verified
                ? "You'll get jobs as soon as the council approves your account. Use Re-check status below."
                : "You'll get jobs once the council approves your account. That usually takes a few minutes."}
            </div>
          )}

          <div className="row" style={{ gap: 10, marginTop: 4, flexWrap: "wrap" }}>
            <button type="button" className="btn primary small grow" onClick={recheck} disabled={polling}>
              {polling ? <Refresh size={16} /> : "2 · Re-check status"}
            </button>
            <button type="button" className="btn outline small" onClick={() => void api.auth.logout()}>
              Sign in as someone else
            </button>
          </div>
        </section>

        {/* Uploader */}
        <section className="card stack" style={{ gap: 14 }}>
          <div className="row between" style={{ alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0, fontSize: 18 }}>1 · Your documents</h2>
            {verified ? (
              <span className="pill green"><Check size={12} /> Aadhaar verified</span>
            ) : uploaded ? (
              <span className="pill amber">Aadhaar with the council</span>
            ) : (
              <span className="pill terracotta">Aadhaar required</span>
            )}
          </div>

          <div className="small muted">
            {verified
              ? "Your Aadhaar is verified. The council is checking your account now."
              : uploaded
                ? "Your Aadhaar is with the council. They mark it verified, then approve you."
                : "The council can only approve you once an Aadhaar is on file and verified. Add it below."}
          </div>

          {carriedError && <div className="notice error">Your Aadhaar did not upload: {carriedError}</div>}

          {workerId !== null ? (
            <UploadSection workerId={workerId} docs={docs} onAdded={loadDocs} />
          ) : (
            <div className="notice">
              This account is not linked to a worker record yet, so documents cannot be uploaded. Ask
              the council to re-check your account.
            </div>
          )}

          {loadingDocs && <div className="small muted">Loading documents…</div>}
        </section>
      </div>
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
        <label className="label" htmlFor="doc-type">Document type</label>
        <select
          id="doc-type"
          className="field"
          value={type}
          onChange={(e) => setType(e.target.value as DocumentKind)}
          style={{ maxWidth: 320 }}
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
        <button className="btn green small" type="submit" disabled={saving || !file || !!fileError} style={{ alignSelf: "flex-start" }}>
          {saving ? "Uploading…" : "Add document"}
        </button>
      </form>

      {docs.length === 0 ? (
        <div className="small muted">No documents on file yet.</div>
      ) : (
        docs.map((d) => (
          <div key={d.id} className="card soft stack" style={{ gap: 6, padding: 12 }}>
            <div className="row between" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span className="small" style={{ fontWeight: 700 }}>
                {DOCUMENT_KIND_LABELS[d.document_type] ?? d.document_type}
                {d.has_content && d.filename ? ` · ${d.filename}` : ""}
              </span>
              {d.verified ? (
                <span className="pill green" style={{ gap: 4 }}><Check size={12} /> verified</span>
              ) : d.rejection_reason ? (
                <span className="pill terracotta" style={{ gap: 4 }}><Cross size={12} /> rejected</span>
              ) : (
                <span className="pill amber">pending council review</span>
              )}
            </div>
            {d.rejection_reason && (
              <div className="tiny" style={{ color: "var(--terracotta-d)" }}>
                {d.rejection_reason} — upload a clear copy above.
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
